#!/usr/bin/env python3
"""
ZMK Daemon-Controlled Mouse Layer

A Python daemon for Ubuntu/Wayland that provides keyboard-driven cursor control
via signal interception. The ZMK keyboard sends F13-F24 keys directly (no modifiers),
and this daemon intercepts them to control the cursor.

Features:
- Movement: F13-F16 for cursor movement (up/down/left/right)
- Precision Mode: Hold F17 to slow down movement
- Scroll Mode: Hold F18 to convert movement to scrolling
- Teleportation: Ctrl+Shift+Alt + F13-F24 for 12 grid positions across 3 screens
- Key Grabbing: F13-F24 are intercepted (prevents OS shortcuts like F13→Settings)
                Other keys are passed through to the OS normally

Requirements:
    pip install evdev screeninfo --break-system-packages

Setup:
    # Enable uinput
    sudo modprobe uinput
    echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf

    # Add user to input group
    sudo usermod -aG input $USER
    # Log out and back in

    # Or run as root:
    sudo python zmk_pointer.py

Usage:
    sudo python zmk_pointer.py --list          # List available keyboards
    sudo python zmk_pointer.py --device 0      # Use keyboard at index 0
    sudo python zmk_pointer.py --no-grab       # Don't grab (F13-F24 reach OS)
"""

import argparse
import select
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import evdev
from evdev import UInput, ecodes, AbsInfo
from screeninfo import get_monitors


# =============================================================================
# Configuration
# =============================================================================

# =============================================================================
# Movement and Mode Configuration
# =============================================================================
# Movement: F13-F16 (up/down/left/right) - no modifiers, daemon intercepts directly
# Mode Modifiers: F17 = precision, F18 = scroll (daemon-side, no ZMK layer needed)
# Teleport: Ctrl+Shift+Alt + F13-F24 for 12 positions across 3 screens

# Movement keys - always F13-F16
MOVEMENT_KEYS: dict[str, tuple[int, int]] = {
    "f13": (0, -1),  # Up
    "f14": (0, 1),  # Down
    "f15": (-1, 0),  # Left
    "f16": (1, 0),  # Right
}

# Mode modifier keys (daemon-side modifiers for movement)
PRECISION_MODE_KEY = "f17"  # Hold for precision mode
SCROLL_MODE_KEY = "f18"  # Hold for scroll mode

# Human-readable names for logging
KEY_DIRECTION_NAMES: dict[str, str] = {
    "f13": "↑ Up",
    "f14": "↓ Down",
    "f15": "← Left",
    "f16": "→ Right",
}

# Mode modifier names for logging
MODE_KEY_NAMES: dict[str, str] = {
    "f17": "🎯 Precision",
    "f18": "📜 Scroll",
}

# Teleport position names for logging
TELEPORT_NAMES: dict[str, str] = {
    "f13": "S1 ↖",
    "f14": "S1 ↗",
    "f15": "S1 ↙",
    "f16": "S1 ↘",
    "f17": "S2 ↖",
    "f18": "S2 ↗",
    "f19": "S2 ↙",
    "f20": "S2 ↘",
    "f21": "S3 ↖",
    "f22": "S3 ↗",
    "f23": "S3 ↙",
    "f24": "S3 ↘",
}

# Teleport keys: F13-F24 (with Alt) map to 12 grid positions across 3 screens
# Layout: 3 screens × (2 cols × 2 rows) = 12 positions
#
# Screen 1        Screen 2        Screen 3
# ┌─────┬─────┐  ┌─────┬─────┐  ┌─────┬─────┐
# │ F13 │ F14 │  │ F17 │ F18 │  │ F21 │ F22 │  ← Top row
# ├─────┼─────┤  ├─────┼─────┤  ├─────┼─────┤
# │ F15 │ F16 │  │ F19 │ F20 │  │ F23 │ F24 │  ← Bottom row
# └─────┴─────┘  └─────┴─────┘  └─────┴─────┘

TELEPORT_KEYS: dict[str, tuple[int, int, int]] = {
    # (screen_index, col, row)
    "f13": (0, 0, 0),  # Screen 1, Top-Left
    "f14": (0, 1, 0),  # Screen 1, Top-Right
    "f15": (0, 0, 1),  # Screen 1, Bottom-Left
    "f16": (0, 1, 1),  # Screen 1, Bottom-Right
    "f17": (1, 0, 0),  # Screen 2, Top-Left
    "f18": (1, 1, 0),  # Screen 2, Top-Right
    "f19": (1, 0, 1),  # Screen 2, Bottom-Left
    "f20": (1, 1, 1),  # Screen 2, Bottom-Right
    "f21": (2, 0, 0),  # Screen 3, Top-Left
    "f22": (2, 1, 0),  # Screen 3, Top-Right
    "f23": (2, 0, 1),  # Screen 3, Bottom-Left
    "f24": (2, 1, 1),  # Screen 3, Bottom-Right
}

# Speed profiles
SPEED_PROFILES: dict[str, dict[str, float]] = {
    "normal": {
        "base": 2.0,
        "max": 10.0,
        "ramp_time": 0.4,
    },
    "precision": {
        "base": 0.5,
        "max": 5.0,
        "ramp_time": 0.6,
    },
}

# Scroll speed
SCROLL_SPEED = 3

# Keycode to character mapping
KEY_MAP: dict[int, str] = {
    # F13-F24 keys for movement and teleport
    ecodes.KEY_F13: "f13",
    ecodes.KEY_F14: "f14",
    ecodes.KEY_F15: "f15",
    ecodes.KEY_F16: "f16",
    ecodes.KEY_F17: "f17",
    ecodes.KEY_F18: "f18",
    ecodes.KEY_F19: "f19",
    ecodes.KEY_F20: "f20",
    ecodes.KEY_F21: "f21",
    ecodes.KEY_F22: "f22",
    ecodes.KEY_F23: "f23",
    ecodes.KEY_F24: "f24",
    # Modifier keys
    ecodes.KEY_LEFTCTRL: "lctrl",
    ecodes.KEY_RIGHTCTRL: "rctrl",
    ecodes.KEY_LEFTSHIFT: "lshift",
    ecodes.KEY_RIGHTSHIFT: "rshift",
    ecodes.KEY_LEFTALT: "lalt",
    ecodes.KEY_RIGHTALT: "ralt",
    ecodes.KEY_LEFTMETA: "lmeta",
    ecodes.KEY_RIGHTMETA: "rmeta",
}

ALL_MODIFIER_KEYS: set[str] = {
    "lctrl",
    "rctrl",
    "lshift",
    "rshift",
    "lalt",
    "ralt",
    "lmeta",
    "rmeta",
}

# F-keys that should be consumed by the daemon (not passed to OS)
# These are grabbed to prevent OS shortcuts (e.g., F13 -> Settings in Ubuntu)
CONSUMED_KEYCODES: set[int] = {
    ecodes.KEY_F13,
    ecodes.KEY_F14,
    ecodes.KEY_F15,
    ecodes.KEY_F16,
    ecodes.KEY_F17,
    ecodes.KEY_F18,
    ecodes.KEY_F19,
    ecodes.KEY_F20,
    ecodes.KEY_F21,
    ecodes.KEY_F22,
    ecodes.KEY_F23,
    ecodes.KEY_F24,
}

# Update rate
UPDATE_RATE_HZ = 120
UPDATE_INTERVAL = 1.0 / UPDATE_RATE_HZ

# Inertia settings
INERTIA_FRICTION = 0.90
INERTIA_MIN_VELOCITY = 0.1


# =============================================================================
# Screen Detection
# =============================================================================


@dataclass
class Monitor:
    """Represents a single monitor."""

    x: int
    y: int
    width: int
    height: int
    name: str = ""

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass
class ScreenLayout:
    """Represents the multi-monitor layout."""

    monitors: list[Monitor]
    min_x: int
    min_y: int
    max_x: int
    max_y: int

    @property
    def width(self) -> int:
        return self.max_x - self.min_x

    @property
    def height(self) -> int:
        return self.max_y - self.min_y


def get_screen_layout() -> ScreenLayout:
    """Detect all monitors and return layout info."""
    raw_monitors = get_monitors()

    if not raw_monitors:
        raise RuntimeError("No monitors detected")

    # Sort monitors left-to-right by x position
    raw_monitors = sorted(raw_monitors, key=lambda m: m.x)

    monitors = [
        Monitor(
            x=m.x, y=m.y, width=m.width, height=m.height, name=m.name or f"Monitor {i}"
        )
        for i, m in enumerate(raw_monitors)
    ]

    min_x = min(m.x for m in monitors)
    min_y = min(m.y for m in monitors)
    max_x = max(m.x + m.width for m in monitors)
    max_y = max(m.y + m.height for m in monitors)

    return ScreenLayout(monitors, min_x, min_y, max_x, max_y)


# =============================================================================
# Virtual Mouse
# =============================================================================


class VirtualMouse:
    """Wrapper for uinput virtual mouse device."""

    def __init__(self, layout: ScreenLayout):
        self.layout = layout

        capabilities = {
            ecodes.EV_REL: [
                ecodes.REL_X,
                ecodes.REL_Y,
                ecodes.REL_WHEEL,
                ecodes.REL_HWHEEL,
            ],
            ecodes.EV_ABS: [
                (ecodes.ABS_X, AbsInfo(0, layout.min_x, layout.max_x, 0, 0, 1)),
                (ecodes.ABS_Y, AbsInfo(0, layout.min_y, layout.max_y, 0, 0, 1)),
            ],
            ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE],
        }

        self.device = UInput(capabilities, name="ZMK-Pointer-Daemon")

    def teleport(self, x: int, y: int) -> None:
        """Move cursor to absolute position using ydotool (Wayland compatible)."""
        try:
            # Use ydotool for Wayland - requires ydotoold daemon running
            subprocess.run(
                ["ydotool", "mousemove", "--absolute", str(x), str(y)],
                check=True,
                capture_output=True,
            )
            # Small jiggle to make cursor visible on unfocused screens
            subprocess.run(
                ["ydotool", "mousemove", "--", "-1", "-1"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["ydotool", "mousemove", "--", "1", "1"],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError:
            # Fallback to uinput ABS (works on X11, may not work on Wayland)
            self.device.write(ecodes.EV_ABS, ecodes.ABS_X, x)
            self.device.write(ecodes.EV_ABS, ecodes.ABS_Y, y)
            self.device.syn()
        except subprocess.CalledProcessError:
            # ydotool failed, try uinput fallback
            self.device.write(ecodes.EV_ABS, ecodes.ABS_X, x)
            self.device.write(ecodes.EV_ABS, ecodes.ABS_Y, y)
            self.device.syn()

    def move_relative(self, dx: int, dy: int) -> None:
        """Move cursor by relative amount."""
        if dx != 0:
            self.device.write(ecodes.EV_REL, ecodes.REL_X, dx)
        if dy != 0:
            self.device.write(ecodes.EV_REL, ecodes.REL_Y, dy)
        if dx != 0 or dy != 0:
            self.device.syn()

    def scroll(self, dx: int, dy: int) -> None:
        """Scroll by amount (dy = vertical, dx = horizontal)."""
        if dy != 0:
            self.device.write(ecodes.EV_REL, ecodes.REL_WHEEL, -dy)
        if dx != 0:
            self.device.write(ecodes.EV_REL, ecodes.REL_HWHEEL, dx)
        if dx != 0 or dy != 0:
            self.device.syn()

    def close(self) -> None:
        """Clean up the virtual device."""
        self.device.close()


# =============================================================================
# Virtual Keyboard (for key passthrough)
# =============================================================================


class VirtualKeyboard:
    """Virtual keyboard for passing through keys that the daemon doesn't consume."""

    def __init__(self, source_device: evdev.InputDevice):
        # Copy capabilities from the source keyboard
        capabilities = source_device.capabilities()
        # Remove EV_SYN as UInput handles it automatically
        capabilities.pop(ecodes.EV_SYN, None)

        self.device = UInput(
            capabilities,
            name="ZMK-Pointer-Passthrough",
            vendor=source_device.info.vendor,
            product=source_device.info.product,
        )

    def write_event(self, event: evdev.InputEvent) -> None:
        """Write an event to the virtual keyboard."""
        self.device.write(event.type, event.code, event.value)
        self.device.syn()

    def close(self) -> None:
        """Clean up the virtual device."""
        self.device.close()


# =============================================================================
# Teleport Grid
# =============================================================================


class TeleportGrid:
    """Handles teleportation to screen grid positions across multiple monitors."""

    def __init__(self, layout: ScreenLayout, cols: int = 2, rows: int = 2):
        self.layout = layout
        self.cols = cols
        self.rows = rows

    def get_coords(self, screen_idx: int, col: int, row: int) -> tuple[int, int]:
        """Calculate center coordinates for a grid cell on a specific screen."""
        monitors = self.layout.monitors

        # Clamp screen index
        if screen_idx >= len(monitors):
            screen_idx = len(monitors) - 1
        if screen_idx < 0:
            screen_idx = 0

        monitor = monitors[screen_idx]

        cell_width = monitor.width / self.cols
        cell_height = monitor.height / self.rows

        x = monitor.x + (col * cell_width) + (cell_width / 2)
        y = monitor.y + (row * cell_height) + (cell_height / 2)

        return (int(x), int(y))

    def get_all_positions(self) -> dict[str, tuple[int, int]]:
        """Get all teleport key positions for display."""
        positions = {}
        for key, (screen_idx, col, row) in TELEPORT_KEYS.items():
            positions[key] = self.get_coords(screen_idx, col, row)
        return positions


# =============================================================================
# Pointer Movement
# =============================================================================


@dataclass
class Pointer:
    """Handles continuous pointer movement with velocity ramping and inertia."""

    mouse: VirtualMouse
    active_keys: set[str] = field(default_factory=set)  # Movement keys (F13-F16)
    held_since: dict[str, float] = field(default_factory=dict)
    accum_x: float = 0.0
    accum_y: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    held_modifiers: set[str] = field(
        default_factory=set
    )  # System modifiers (Alt, Ctrl, etc.)
    mode_keys: set[str] = field(default_factory=set)  # Mode modifiers (F17, F18)
    scroll_accum_x: float = 0.0
    scroll_accum_y: float = 0.0

    @property
    def is_precision_mode(self) -> bool:
        """Precision mode is active when F17 is held."""
        return PRECISION_MODE_KEY in self.mode_keys

    @property
    def is_scroll_mode(self) -> bool:
        """Scroll mode is active when F18 is held."""
        return SCROLL_MODE_KEY in self.mode_keys

    @property
    def is_teleport_activated(self) -> bool:
        """Teleport is activated when Alt is held."""
        return "lalt" in self.held_modifiers or "ralt" in self.held_modifiers

    def set_modifier(self, key: str, pressed: bool) -> None:
        """Update modifier key state."""
        if key in ALL_MODIFIER_KEYS:
            if pressed:
                self.held_modifiers.add(key)
            else:
                self.held_modifiers.discard(key)

    def set_mode_key(self, key: str, pressed: bool) -> None:
        """Update mode modifier key state (F17, F18)."""
        if pressed:
            self.mode_keys.add(key)
        else:
            self.mode_keys.discard(key)

    def get_held_modifiers_str(self) -> str:
        """Get string representation of held modifiers."""
        if not self.held_modifiers:
            return "none"
        return "+".join(sorted(self.held_modifiers))

    def press(self, key: str) -> None:
        """Register a key press."""
        if key not in self.active_keys:
            self.active_keys.add(key)
            self.held_since[key] = time.perf_counter()
            # Reset velocity and accumulators to prevent direction change issues
            self.velocity_x = 0.0
            self.velocity_y = 0.0
            self.accum_x = 0.0
            self.accum_y = 0.0

    def release(self, key: str) -> None:
        """Register a key release."""
        self.active_keys.discard(key)
        self.held_since.pop(key, None)

    def release_all(self) -> None:
        """Release all movement keys."""
        self.active_keys.clear()
        self.held_since.clear()
        self.velocity_x = 0.0
        self.velocity_y = 0.0

    @staticmethod
    def calculate_speed(hold_duration: float, profile: dict[str, float]) -> float:
        """Calculate speed with cubic ease-out ramping."""
        t = min(hold_duration / profile["ramp_time"], 1.0)
        eased = 1.0 - (1.0 - t) ** 3
        return profile["base"] + (profile["max"] - profile["base"]) * eased

    def update(self) -> bool:
        """Update pointer position based on active keys. Returns True if movement occurred."""
        now = time.perf_counter()

        # Calculate input direction from movement keys (F13-F16)
        input_dx = 0.0
        input_dy = 0.0

        # Determine speed profile based on mode
        profile = (
            SPEED_PROFILES["precision"]
            if self.is_precision_mode
            else SPEED_PROFILES["normal"]
        )

        for key in self.active_keys:
            if key in MOVEMENT_KEYS:
                direction = MOVEMENT_KEYS[key]
                hold_duration = now - self.held_since.get(key, now)
                speed = self.calculate_speed(hold_duration, profile)
                input_dx += direction[0] * speed
                input_dy += direction[1] * speed

        # Handle scroll mode - convert movement to scroll
        if self.is_scroll_mode and (input_dx != 0 or input_dy != 0):
            self.scroll_accum_x += input_dx * UPDATE_INTERVAL * 10
            self.scroll_accum_y += input_dy * UPDATE_INTERVAL * 10

            scroll_x = int(self.scroll_accum_x)
            scroll_y = int(self.scroll_accum_y)

            if scroll_x != 0 or scroll_y != 0:
                self.mouse.scroll(scroll_x, scroll_y)
                self.scroll_accum_x -= scroll_x
                self.scroll_accum_y -= scroll_y
            return scroll_x != 0 or scroll_y != 0

        # Normalize diagonal input
        if input_dx != 0 and input_dy != 0:
            magnitude = (input_dx**2 + input_dy**2) ** 0.5
            target_speed = max(abs(input_dx), abs(input_dy))
            input_dx = input_dx / magnitude * target_speed
            input_dy = input_dy / magnitude * target_speed

        # Update velocity
        if input_dx != 0 or input_dy != 0:
            self.velocity_x = input_dx
            self.velocity_y = input_dy
        else:
            self.velocity_x *= INERTIA_FRICTION
            self.velocity_y *= INERTIA_FRICTION

            if abs(self.velocity_x) < INERTIA_MIN_VELOCITY:
                self.velocity_x = 0.0
            if abs(self.velocity_y) < INERTIA_MIN_VELOCITY:
                self.velocity_y = 0.0

        if self.velocity_x == 0 and self.velocity_y == 0:
            return False

        # Sub-pixel accumulation
        self.accum_x += self.velocity_x
        self.accum_y += self.velocity_y

        move_x = int(self.accum_x)
        move_y = int(self.accum_y)

        if move_x != 0 or move_y != 0:
            self.mouse.move_relative(move_x, move_y)
            self.accum_x -= move_x
            self.accum_y -= move_y
            return True

        return False


# =============================================================================
# Keyboard Input
# =============================================================================


def list_keyboards() -> list[evdev.InputDevice]:
    """Find all keyboard devices."""
    keyboards = []
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        caps = dev.capabilities()
        if ecodes.EV_KEY in caps and ecodes.KEY_A in caps.get(ecodes.EV_KEY, []):
            keyboards.append(dev)
    return keyboards


def print_keyboards(keyboards: list[evdev.InputDevice]) -> None:
    """Print list of available keyboards."""
    print("\nAvailable keyboards:")
    print("-" * 60)
    for i, kb in enumerate(keyboards):
        print(f"  [{i}] {kb.name}")
        print(f"      Path: {kb.path}")
    print("-" * 60)
    print()


def find_keyboard(device_index: Optional[int] = None) -> evdev.InputDevice:
    """Find keyboard device by index or return first one. Prefers SHSH52 keyboard."""
    keyboards = list_keyboards()

    if not keyboards:
        raise RuntimeError("No keyboard found")

    if device_index is not None:
        if 0 <= device_index < len(keyboards):
            return keyboards[device_index]
        else:
            raise RuntimeError(
                f"Invalid device index {device_index}. Found {len(keyboards)} keyboards."
            )

    # Prefer HSHS52 keyboard if available
    for kb in keyboards:
        if "HSHS52" in kb.name:
            return kb

    return keyboards[0]


def get_key_char(code: int) -> Optional[str]:
    """Convert keycode to character."""
    return KEY_MAP.get(code)


# =============================================================================
# Event Handling
# =============================================================================


def handle_key_event(
    event: evdev.InputEvent,
    pointer: Pointer,
    teleport_grid: TeleportGrid,
    mouse: VirtualMouse,
    debug: bool = True,
) -> None:
    """Handle a keyboard event."""
    key_char = get_key_char(event.code)
    if key_char is None:
        return

    pressed = event.value != 0
    is_press = event.value == 1

    timestamp = time.strftime("%H:%M:%S")

    # Handle system modifier keys (track Alt for teleport detection)
    if key_char in ALL_MODIFIER_KEYS:
        pointer.set_modifier(key_char, pressed)
        if debug:
            mod_state = pointer.get_held_modifiers_str()
            if pressed:
                print(f"[{timestamp}] 🔑 Modifier: {key_char} (held: {mod_state})")
        return

    # Handle mode modifier keys (F17 = precision, F18 = scroll)
    # Note: These only affect movement, not teleport
    if key_char in (PRECISION_MODE_KEY, SCROLL_MODE_KEY):
        # If Alt is held, this is a teleport key, not a mode modifier
        if not pointer.is_teleport_activated:
            pointer.set_mode_key(key_char, pressed)
            if debug:
                mode_name = MODE_KEY_NAMES.get(key_char, key_char)
                state = "ON" if pressed else "OFF"
                print(f"[{timestamp}] {mode_name} mode {state}")
            return

    # Handle teleport keys (when Alt is held, F13-F24 become teleport)
    if is_press and key_char in TELEPORT_KEYS and pointer.is_teleport_activated:
        screen_idx, col, row = TELEPORT_KEYS[key_char]
        coords = teleport_grid.get_coords(screen_idx, col, row)
        mouse.teleport(*coords)
        if debug:
            pos_name = TELEPORT_NAMES.get(key_char, key_char)
            print(f"[{timestamp}] 📍 Teleport: {pos_name} → {coords}")
        return

    # Handle movement keys (F13-F16)
    if key_char in MOVEMENT_KEYS:
        if pressed:
            pointer.press(key_char)
            if debug and is_press:
                direction_name = KEY_DIRECTION_NAMES.get(key_char, key_char)
                mode = (
                    "[scroll]"
                    if pointer.is_scroll_mode
                    else "[precision]" if pointer.is_precision_mode else ""
                )
                print(f"[{timestamp}] 🖱️  Move: {direction_name} {mode}")
        else:
            pointer.release(key_char)
            if debug:
                direction_name = KEY_DIRECTION_NAMES.get(key_char, key_char)
                print(f"[{timestamp}] 🛑 Release: {direction_name}")


# =============================================================================
# Main
# =============================================================================


def print_startup_info(layout: ScreenLayout, grid: TeleportGrid) -> None:
    """Print startup information."""
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║         ZMK Daemon-Controlled Mouse Layer                    ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    print(f"📺 Detected {len(layout.monitors)} monitor(s):")
    for i, m in enumerate(layout.monitors):
        print(f"   Screen {i + 1}: {m.width}x{m.height} at ({m.x}, {m.y}) - {m.name}")
    print()

    print("🎯 Activation:")
    print("   Movement: direct F13-F18 signals from the keyboard")
    print("   Teleport: hold Alt while pressing a teleport key")
    print()

    print("🕹️  Movement (Left Hand):")
    print("       ┌───┐")
    print("       │ W │  ↑")
    print("   ┌───┼───┼───┐")
    print("   │ A │   │ D │  ← →")
    print("   └───┼───┼───┘")
    print("       │ S │  ↓")
    print("       └───┘")
    print()

    print("📍 Teleport Grid (F13-F24):")
    print("   Screen 1      Screen 2      Screen 3")
    print("   ┌─────┬─────┐ ┌─────┬─────┐ ┌─────┬─────┐")
    print("   │ F13 │ F14 │ │ F17 │ F18 │ │ F21 │ F22 │")
    print("   ├─────┼─────┤ ├─────┼─────┤ ├─────┼─────┤")
    print("   │ F15 │ F16 │ │ F19 │ F20 │ │ F23 │ F24 │")
    print("   └─────┴─────┘ └─────┴─────┘ └─────┴─────┘")
    print()

    positions = grid.get_all_positions()
    print("   Teleport coordinates:")
    for key in ["f13", "f14", "f15", "f16"]:
        if key in positions:
            print(f"     {key.upper()} → {positions[key]}")

    print()
    print("🎮 Modes (hold modifier while moving):")
    print("   Normal:    F13-F16 movement")
    print("   Precision: Hold F17 + movement - slower")
    print("   Scroll:    Hold F18 + movement - scroll instead of move")
    print()
    print("📍 Teleport (Ctrl+Shift+Alt + F-key):")
    print("   Screen 1: Ctrl+Shift+Alt + F13-F16")
    print("   Screen 2: Ctrl+Shift+Alt + F17-F20")
    print("   Screen 3: Ctrl+Shift+Alt + F21-F24")
    print()
    print("Listening... (Ctrl+C to exit)")
    print()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="ZMK Daemon-Controlled Mouse Layer")
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available keyboard devices and exit",
    )
    parser.add_argument(
        "--device",
        "-d",
        type=int,
        default=None,
        help="Index of keyboard device to use (see --list)",
    )
    parser.add_argument(
        "--no-grab",
        action="store_true",
        help="Don't grab keyboard (F13-F24 will reach the OS)",
    )
    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="Disable debug output",
    )
    args = parser.parse_args()

    if args.list:
        keyboards = list_keyboards()
        if not keyboards:
            print("No keyboards found!")
            sys.exit(1)
        print_keyboards(keyboards)
        sys.exit(0)

    try:
        layout = get_screen_layout()
    except RuntimeError as e:
        print(f"Error detecting screens: {e}")
        return

    mouse = VirtualMouse(layout)
    grid = TeleportGrid(layout)
    pointer = Pointer(mouse=mouse)

    try:
        keyboard = find_keyboard(args.device)
        print(f"Using keyboard: {keyboard.name}")
    except RuntimeError as e:
        print(f"Error: {e}")
        mouse.close()
        return

    # Create virtual keyboard for passthrough (before grabbing)
    virtual_kb: Optional[VirtualKeyboard] = None
    grab_enabled = not args.no_grab

    if grab_enabled:
        virtual_kb = VirtualKeyboard(keyboard)
        keyboard.grab()
        print("Keyboard grabbed - F13-F24 intercepted, other keys passed through")

    print_startup_info(layout, grid)

    last_update = time.perf_counter()
    debug = not args.no_debug

    try:
        while True:
            r, _, _ = select.select([keyboard], [], [], 0.001)

            if r:
                for event in keyboard.read():
                    if event.type == ecodes.EV_KEY:
                        handle_key_event(event, pointer, grid, mouse, debug)
                        # Pass through keys that aren't consumed by the daemon
                        if (
                            grab_enabled
                            and virtual_kb
                            and event.code not in CONSUMED_KEYCODES
                        ):
                            virtual_kb.write_event(event)
                    elif grab_enabled and virtual_kb:
                        # Pass through non-key events (EV_MSC, etc.)
                        virtual_kb.write_event(event)

            now = time.perf_counter()
            if now - last_update >= UPDATE_INTERVAL:
                pointer.update()
                last_update = now

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if grab_enabled:
            keyboard.ungrab()
        if virtual_kb:
            virtual_kb.close()
        mouse.close()
        print("Cleanup complete.")


if __name__ == "__main__":
    main()
