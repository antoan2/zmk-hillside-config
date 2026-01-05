#!/usr/bin/env python3
"""
Mouse Trainer - A tool to practice quick mouse movements and teleportation.
Four training modes available:
1. Teleport to Zone - Teleport to one of 12 highlighted zones (4 per screen)
2. Teleport to Target - Target appears, teleport to its zone (12 zones)
3. Click in Zone - Random zone appears, click inside it
4. Click Target - Small target appears anywhere, click it precisely

Supports multi-monitor setups with offsets - spawns window covering all screens
but only places targets within actual screen boundaries.
"""

import tkinter as tk
from tkinter import simpledialog
import random
import time
import os
from datetime import datetime

# Try to import screeninfo for multi-monitor support
try:
    from screeninfo import get_monitors

    HAS_SCREENINFO = True
except ImportError:
    HAS_SCREENINFO = False
    print(
        "Note: Install 'screeninfo' package for multi-monitor support: pip install screeninfo"
    )


# Training modes
MODE_TELEPORT_ZONE = 1  # Teleport to one of 12 highlighted zones
MODE_TELEPORT_TARGET = 2  # Target visible, teleport to its zone
MODE_CLICK_IN_ZONE = 3  # Click inside random highlighted zone
MODE_CLICK_TARGET = 4  # Click small target anywhere

MODE_NAMES = {
    MODE_TELEPORT_ZONE: "Teleport to Zone",
    MODE_TELEPORT_TARGET: "Teleport to Target",
    MODE_CLICK_IN_ZONE: "Click in Zone",
    MODE_CLICK_TARGET: "Click Target",
}

MODE_DESCRIPTIONS = {
    MODE_TELEPORT_ZONE: "Teleport to the highlighted zone (12 zones)",
    MODE_TELEPORT_TARGET: "Teleport to zone containing the target",
    MODE_CLICK_IN_ZONE: "Click anywhere inside the random zone",
    MODE_CLICK_TARGET: "Click the small target button",
}


class MouseTrainer:
    def __init__(self):
        print("=" * 60)
        print("MOUSE TRAINER STARTUP")
        print("=" * 60)

        self.root = tk.Tk()
        self.root.title("Mouse Trainer")
        self.root.configure(bg="#2b2b2b")

        # Need to update before getting screen info
        self.root.update_idletasks()
        print("[DEBUG] Initial window info:")
        print(f"  winfo_screenwidth: {self.root.winfo_screenwidth()}")
        print(f"  winfo_screenheight: {self.root.winfo_screenheight()}")

        # Get monitor information and calculate window bounds
        self.monitors = []
        self.screen_regions = []  # Valid regions where buttons can spawn
        self.setup_multi_monitor()

        # Calculate teleport zones (12 fixed zones: 4 per screen, linked to zmk_pointer teleport)
        self.teleport_zones = []  # 12 fixed zones for modes 1 & 2
        self.zone_cols = 2  # 2 columns per screen
        self.zone_rows = 2  # 2 rows per screen = 4 zones per screen
        self.setup_teleport_zones()

        # Calculate geometry - we want window slightly larger than total screen area
        self.padding = 10
        self.target_width = self.window_width + self.padding * 2
        self.target_height = self.window_height + self.padding * 2
        self.target_x = max(0, self.window_x - self.padding)
        self.target_y = max(0, self.window_y - self.padding)

        print("[DEBUG] Target geometry:")
        print(
            f"  target_width: {self.target_width}, target_height: {self.target_height}"
        )
        print(f"  target_x: {self.target_x}, target_y: {self.target_y}")

        # For multi-monitor spanning, we can't use -fullscreen as it only covers one screen
        # Instead, set geometry to span all monitors and use -topmost to stay on top
        # Keep window decorations minimal but allow taskbar and Alt+F4

        # Set initial geometry
        self.root.geometry(
            f"{self.target_width}x{self.target_height}+{self.target_x}+{self.target_y}"
        )

        # Set window to stay on top
        self.root.attributes("-topmost", True)

        # Remove window decorations but keep in taskbar (type hint)
        # On X11/Linux, we can set window type to make it borderless but still managed
        try:
            self.root.attributes(
                "-type", "splash"
            )  # Splash windows have no decorations
        except tk.TclError:
            # Fallback for systems that don't support -type
            pass

        # Handle window close button (X)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Keybindings
        self.root.bind("<Escape>", lambda e: self.on_close())
        self.root.bind("<q>", lambda e: self.on_close())
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<s>", self.open_settings)

        # Mode switching with 1, 2, 3, 4 keys (no Ctrl needed for simplicity)
        self.root.bind("<Key-1>", lambda e: self.set_mode(MODE_TELEPORT_ZONE))
        self.root.bind("<Key-2>", lambda e: self.set_mode(MODE_TELEPORT_TARGET))
        self.root.bind("<Key-3>", lambda e: self.set_mode(MODE_CLICK_IN_ZONE))
        self.root.bind("<Key-4>", lambda e: self.set_mode(MODE_CLICK_TARGET))
        # Also try with keypad
        self.root.bind("<KP_1>", lambda e: self.set_mode(MODE_TELEPORT_ZONE))
        self.root.bind("<KP_2>", lambda e: self.set_mode(MODE_TELEPORT_TARGET))
        self.root.bind("<KP_3>", lambda e: self.set_mode(MODE_CLICK_IN_ZONE))
        self.root.bind("<KP_4>", lambda e: self.set_mode(MODE_CLICK_TARGET))

        # Ensure the window gets focus for keyboard events
        self.root.focus_force()
        self.root.lift()

        self.root.update_idletasks()
        print("[DEBUG] After setup:")
        print(f"  winfo_geometry: {self.root.winfo_geometry()}")

        # Circular button dimensions
        self.button_radius = 25
        self.target_radius = 15  # Smaller target for teleport mode

        # Training mode
        self.current_mode = MODE_TELEPORT_ZONE

        # Round settings
        self.clicks_per_round = 5
        self.current_clicks = 0
        self.round_start_time = None
        self.waiting_for_start = True

        # Current target zone for teleport modes
        self.current_zone = None
        self.zone_highlight = None

        # Times history (per mode)
        self.round_times = {mode: [] for mode in MODE_NAMES}
        self.log_file = os.path.join(os.path.dirname(__file__), "round_times.log")
        self.load_times_from_log()

        # Bind space to start round
        self.root.bind("<space>", self.start_round)

        # Create UI elements
        self.create_ui()

        # Mouse motion tracking for teleport modes
        self.root.bind("<Motion>", self.on_mouse_motion)

        # Bind window resize to update boundaries
        self.root.bind("<Configure>", self.on_resize)

    def on_close(self):
        """Handle window close."""
        print("[DEBUG] Closing window")
        self.root.destroy()

    def setup_teleport_zones(self):
        """Setup teleport zones based on screen regions."""
        self.teleport_zones = []

        print("[DEBUG] Screen regions for teleport zones:")
        for i, region in enumerate(self.screen_regions):
            print(
                f"  Region {i+1} ({region['name']}): x={region['x']}, y={region['y']}, "
                f"w={region['width']}, h={region['height']}"
            )

        # For each screen region, create a grid of zones
        for region in self.screen_regions:
            zone_width = region["width"] // self.zone_cols
            zone_height = region["height"] // self.zone_rows

            for row in range(self.zone_rows):
                for col in range(self.zone_cols):
                    zone = {
                        "x": region["x"] + col * zone_width,
                        "y": region["y"] + row * zone_height,
                        "width": zone_width,
                        "height": zone_height,
                        "row": row,
                        "col": col,
                        "screen": region["name"],
                    }
                    self.teleport_zones.append(zone)
                    print(
                        f"  Zone {len(self.teleport_zones)}: screen={region['name']}, "
                        f"x={zone['x']}, y={zone['y']}, w={zone_width}, h={zone_height}"
                    )

        print(f"[DEBUG] Created {len(self.teleport_zones)} teleport zones")

    def set_mode(self, mode):
        """Change the current training mode."""
        if not self.waiting_for_start:
            return  # Don't change mode during a round

        self.current_mode = mode
        self.update_mode_display()
        self.update_times_display()
        print(f"[MODE] Switched to: {MODE_NAMES[mode]}")

    def open_settings(self, event=None):
        """Open settings dialog."""
        if not self.waiting_for_start:
            return  # Don't open settings during a round

        # Create settings dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.configure(bg="#3b3b3b")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 300) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 150) // 2
        dialog.geometry(f"+{x}+{y}")

        # Rounds per session setting
        tk.Label(
            dialog,
            text="Number of targets per round:",
            font=("Arial", 12),
            bg="#3b3b3b",
            fg="white",
        ).pack(pady=(20, 5))

        rounds_var = tk.StringVar(value=str(self.clicks_per_round))
        rounds_entry = tk.Entry(
            dialog,
            textvariable=rounds_var,
            font=("Arial", 12),
            width=10,
            justify="center",
        )
        rounds_entry.pack(pady=5)
        rounds_entry.select_range(0, tk.END)
        rounds_entry.focus_set()

        def save_settings():
            try:
                new_rounds = int(rounds_var.get())
                if 1 <= new_rounds <= 100:
                    self.clicks_per_round = new_rounds
                    self.progress_label.config(
                        text=f"Progress: 0/{self.clicks_per_round}"
                    )
                    print(f"[SETTINGS] Targets per round set to: {new_rounds}")
            except ValueError:
                pass
            dialog.destroy()

        def on_enter(event):
            save_settings()

        rounds_entry.bind("<Return>", on_enter)

        tk.Button(
            dialog,
            text="Save",
            command=save_settings,
            font=("Arial", 11),
            bg="#4CAF50",
            fg="white",
            padx=20,
            pady=5,
        ).pack(pady=15)

    def setup_multi_monitor(self):
        """Detect monitors and calculate window bounds and valid button regions."""
        self.center_screen = (
            None  # Will store the center screen region for HUD placement
        )

        if HAS_SCREENINFO:
            try:
                monitors = get_monitors()
                if monitors:
                    self.monitors = monitors

                    # Calculate the bounding box of all monitors
                    min_x = min(m.x for m in monitors)
                    min_y = min(m.y for m in monitors)
                    max_x = max(m.x + m.width for m in monitors)
                    max_y = max(m.y + m.height for m in monitors)

                    # Store window position and size (covering all monitors)
                    self.window_x = min_x
                    self.window_y = min_y
                    self.window_width = max_x - min_x
                    self.window_height = max_y - min_y

                    # Store valid screen regions (relative to window position)
                    # These are the actual screen areas where buttons can spawn
                    for m in monitors:
                        region = {
                            "x": m.x - min_x,  # Convert to window-relative coords
                            "y": m.y - min_y,
                            "width": m.width,
                            "height": m.height,
                            "name": m.name if hasattr(m, "name") else "Unknown",
                        }
                        self.screen_regions.append(region)

                    # Find the middle screen (physically in the center when sorted by x position)
                    # Sort regions by x position to find the one in the middle
                    sorted_regions = sorted(self.screen_regions, key=lambda r: r["x"])

                    if len(sorted_regions) >= 3:
                        # With 3 or more screens, pick the middle one
                        middle_index = len(sorted_regions) // 2
                        center_region = sorted_regions[middle_index]
                    elif len(sorted_regions) == 2:
                        # With 2 screens, pick the first one (left)
                        center_region = sorted_regions[0]
                    else:
                        # Single screen
                        center_region = (
                            sorted_regions[0]
                            if sorted_regions
                            else self.screen_regions[0]
                        )

                    print(
                        f"[DEBUG] Sorted screens by x: {[r['name'] + ' (x=' + str(r['x']) + ')' for r in sorted_regions]}"
                    )
                    print(f"[DEBUG] Selected middle screen: {center_region['name']}")

                    self.center_screen = center_region

                    print(f"Detected {len(monitors)} monitor(s):")
                    for i, m in enumerate(monitors):
                        print(
                            f"  Monitor {i+1}: {m.width}x{m.height} at ({m.x}, {m.y})"
                        )
                    print(
                        f"Window bounds: {self.window_width}x{self.window_height} at ({self.window_x}, {self.window_y})"
                    )
                    print(
                        f"Center screen for HUD: {self.center_screen['name']} at ({self.center_screen['x']}, {self.center_screen['y']})"
                    )
                    return
            except Exception as e:
                print(f"Error detecting monitors: {e}")

        # Fallback to single monitor mode
        self.root.update_idletasks()
        self.window_x = 0
        self.window_y = 0
        self.window_width = self.root.winfo_screenwidth()
        self.window_height = self.root.winfo_screenheight()
        self.screen_regions = [
            {
                "x": 0,
                "y": 0,
                "width": self.window_width,
                "height": self.window_height,
                "name": "Primary",
            }
        ]
        self.center_screen = self.screen_regions[0]
        print(f"Single monitor mode: {self.window_width}x{self.window_height}")

    def toggle_fullscreen(self, event=None):
        """Toggle between fullscreen and windowed mode."""
        try:
            current = self.root.attributes("-fullscreen")
            self.root.attributes("-fullscreen", not current)
            if current:
                # Going to windowed mode
                self.root.geometry("800x600+100+100")
            print(f"[DEBUG] Fullscreen toggled to: {not current}")
        except Exception as e:
            print(f"Toggle error: {e}")

    def create_ui(self):
        """Create all UI elements."""
        # Main canvas for zone highlighting (must be created first, behind everything)
        self.main_canvas = tk.Canvas(self.root, bg="#2b2b2b", highlightthickness=0)
        self.main_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        # Bind click on main canvas for mode 3 (click in zone)
        self.main_canvas.bind("<Button-1>", self.on_zone_click)

        # Get center screen position for HUD placement
        cs = self.center_screen
        cs_center_x = cs["x"] + cs["width"] // 2
        cs_center_y = cs["y"] + cs["height"] // 2

        # Top frame for keybindings info (on center screen)
        self.keybindings_frame = tk.Frame(self.root, bg="#1a1a1a")
        self.keybindings_frame.place(x=cs_center_x, y=cs["y"] + 5, anchor=tk.N)

        keybindings_text = (
            "ESC: Quit  |  SPACE: Start Round  |  S: Settings  |  1/2/3/4: Switch Mode"
        )
        self.keybindings_label = tk.Label(
            self.keybindings_frame,
            text=keybindings_text,
            font=("Arial", 11),
            bg="#1a1a1a",
            fg="#888888",
            padx=15,
            pady=5,
        )
        self.keybindings_label.pack()

        # Left frame for modes (on center screen left edge)
        self.modes_frame = tk.Frame(self.root, bg="#3b3b3b", padx=15, pady=10)
        self.modes_frame.place(x=cs["x"] + 10, y=cs_center_y, anchor=tk.W)

        self.modes_title = tk.Label(
            self.modes_frame,
            text="Training Modes",
            font=("Arial", 12, "bold"),
            bg="#3b3b3b",
            fg="#FFD700",
        )
        self.modes_title.pack(pady=(0, 10))

        # Mode labels
        self.mode_labels = {}
        for mode_num in [
            MODE_TELEPORT_ZONE,
            MODE_TELEPORT_TARGET,
            MODE_CLICK_IN_ZONE,
            MODE_CLICK_TARGET,
        ]:
            frame = tk.Frame(self.modes_frame, bg="#3b3b3b")
            frame.pack(anchor=tk.W, pady=3)

            shortcut = tk.Label(
                frame,
                text=f"[{mode_num}]",
                font=("Arial", 10, "bold"),
                bg="#3b3b3b",
                fg="#6699CC",
                width=4,
                anchor=tk.W,
            )
            shortcut.pack(side=tk.LEFT)

            label = tk.Label(
                frame,
                text=MODE_NAMES[mode_num],
                font=("Arial", 10),
                bg="#3b3b3b",
                fg="white",
            )
            label.pack(side=tk.LEFT)
            self.mode_labels[mode_num] = label

        # Separator
        tk.Frame(self.modes_frame, bg="#555555", height=1).pack(fill=tk.X, pady=10)

        # Current mode indicator
        self.current_mode_label = tk.Label(
            self.modes_frame,
            text=f"Active: {MODE_NAMES[self.current_mode]}",
            font=("Arial", 10, "bold"),
            bg="#3b3b3b",
            fg="#4CAF50",
        )
        self.current_mode_label.pack(pady=(0, 5))

        # Mode description
        self.mode_desc_label = tk.Label(
            self.modes_frame,
            text=MODE_DESCRIPTIONS[self.current_mode],
            font=("Arial", 9),
            bg="#3b3b3b",
            fg="#aaaaaa",
            wraplength=150,
        )
        self.mode_desc_label.pack()

        # Top frame for status info (below keybindings, on center screen)
        self.top_frame = tk.Frame(self.root, bg="#2b2b2b")
        self.top_frame.place(x=cs_center_x, y=cs["y"] + 50, anchor=tk.N)

        # Current mode display (prominent)
        self.mode_display_label = tk.Label(
            self.top_frame,
            text=f"Mode: {MODE_NAMES[self.current_mode]}",
            font=("Arial", 14, "bold"),
            bg="#2b2b2b",
            fg="#4CAF50",
        )
        self.mode_display_label.pack(pady=2)

        # Status label
        self.status_label = tk.Label(
            self.top_frame,
            text="Press SPACE to start a round",
            font=("Arial", 18, "bold"),
            bg="#2b2b2b",
            fg="#FFD700",
        )
        self.status_label.pack(pady=5)

        # Progress label
        self.progress_label = tk.Label(
            self.top_frame,
            text=f"Progress: 0/{self.clicks_per_round}",
            font=("Arial", 14),
            bg="#2b2b2b",
            fg="white",
        )
        self.progress_label.pack(pady=5)

        # Times frame on the right side (on center screen right edge)
        self.times_frame = tk.Frame(self.root, bg="#3b3b3b", padx=15, pady=10)
        self.times_frame.place(x=cs["x"] + cs["width"] - 10, y=cs_center_y, anchor=tk.E)

        self.times_title = tk.Label(
            self.times_frame,
            text="Last 10 Times",
            font=("Arial", 12, "bold"),
            bg="#3b3b3b",
            fg="#FFD700",
        )
        self.times_title.pack(pady=(0, 10))

        self.times_labels = []
        for i in range(10):
            label = tk.Label(
                self.times_frame, text="-", font=("Arial", 11), bg="#3b3b3b", fg="white"
            )
            label.pack(anchor=tk.W)
            self.times_labels.append(label)

        self.update_times_display()

        # Create canvas for circular button/target
        self.canvas = tk.Canvas(
            self.root,
            width=self.button_radius * 2 + 4,
            height=self.button_radius * 2 + 4,
            bg="#2b2b2b",
            highlightthickness=0,
        )

        # Draw circular button
        self.button_id = self.canvas.create_oval(
            2,
            2,
            self.button_radius * 2 + 2,
            self.button_radius * 2 + 2,
            fill="#4CAF50",
            outline="#45a049",
            width=3,
        )

        # Add text to button
        self.button_text = self.canvas.create_text(
            self.button_radius + 2,
            self.button_radius + 2,
            text="GO!",
            font=("Arial", 14, "bold"),
            fill="white",
        )

        # Bind click events to the circle
        self.canvas.tag_bind(self.button_id, "<Button-1>", self.on_button_click)
        self.canvas.tag_bind(self.button_text, "<Button-1>", self.on_button_click)

        # Hide canvas initially
        self.canvas.place_forget()

        # Create target canvas for teleport modes (with crosshair)
        # Make it larger to accommodate the crosshair lines
        self.crosshair_size = (
            200  # Total size of crosshair area (larger for visibility)
        )
        self.target_canvas = tk.Canvas(
            self.root,
            width=self.crosshair_size * 2,
            height=self.crosshair_size * 2,
            bg="#2b2b2b",
            highlightthickness=0,
        )

        # Draw crosshair lines (horizontal and vertical through center)
        center = self.crosshair_size
        # Vertical line - thick and visible
        self.crosshair_v = self.target_canvas.create_line(
            center,
            0,
            center,
            self.crosshair_size * 2,
            fill="#FF6B6B",
            width=3,
            dash=(12, 6),
        )
        # Horizontal line - thick and visible
        self.crosshair_h = self.target_canvas.create_line(
            0,
            center,
            self.crosshair_size * 2,
            center,
            fill="#FF6B6B",
            width=3,
            dash=(12, 6),
        )

        # Draw target circle in the center
        self.target_id = self.target_canvas.create_oval(
            center - self.target_radius,
            center - self.target_radius,
            center + self.target_radius,
            center + self.target_radius,
            fill="#FF6B6B",
            outline="#FFFFFF",
            width=3,
        )

        # Draw inner dot for precision
        inner_dot_radius = 4
        self.target_inner = self.target_canvas.create_oval(
            center - inner_dot_radius,
            center - inner_dot_radius,
            center + inner_dot_radius,
            center + inner_dot_radius,
            fill="#FFFFFF",
            outline="#FFFFFF",
        )

        # Bind click events ONLY to the target circle elements (for Mode 4 - Click Target)
        # This ensures clicks must be on the actual target, not just anywhere on the canvas
        self.target_canvas.tag_bind(self.target_id, "<Button-1>", self.on_button_click)
        self.target_canvas.tag_bind(
            self.target_inner, "<Button-1>", self.on_button_click
        )
        # Do NOT bind to the whole canvas - only the target circle should be clickable

        # Bind motion to target_canvas so teleport detection works when mouse is over it
        self.target_canvas.bind("<Motion>", self.on_mouse_motion)

        # Hide target canvas initially
        self.target_canvas.place_forget()

    def update_mode_display(self):
        """Update the mode display in the left panel and top display."""
        # Update current mode label in left panel
        self.current_mode_label.config(text=f"Active: {MODE_NAMES[self.current_mode]}")
        self.mode_desc_label.config(text=MODE_DESCRIPTIONS[self.current_mode])

        # Update prominent mode display at top
        self.mode_display_label.config(text=f"Mode: {MODE_NAMES[self.current_mode]}")

        # Highlight active mode in left panel
        for mode_num, label in self.mode_labels.items():
            if mode_num == self.current_mode:
                label.config(fg="#4CAF50", font=("Arial", 10, "bold"))
            else:
                label.config(fg="white", font=("Arial", 10))

    def load_times_from_log(self):
        """Load previous times from log file."""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r") as f:
                    lines = f.readlines()
                    for line in lines[
                        -50:
                    ]:  # Get last 50 entries to have enough for all modes
                        parts = line.strip().split(" - ")
                        if len(parts) >= 2:
                            # Parse mode from log if present
                            mode = MODE_CLICK_IN_ZONE  # Default for old logs
                            time_str = parts[1]

                            # Check if mode is specified in brackets
                            if "[" in time_str and "]" in time_str:
                                mode_start = time_str.index("[") + 1
                                mode_end = time_str.index("]")
                                mode_name = time_str[mode_start:mode_end]
                                time_str = time_str[mode_end + 2 :].strip()  # Skip "] "

                                # Find mode by name
                                for m, name in MODE_NAMES.items():
                                    if name == mode_name:
                                        mode = m
                                        break

                            time_str = time_str.replace("s", "")
                            try:
                                self.round_times[mode].append(float(time_str))
                            except (ValueError, KeyError):
                                pass
            except Exception as e:
                print(f"[DEBUG] Error loading log: {e}")

    def log_round_time(self, round_time):
        """Log round time to file with mode."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mode_name = MODE_NAMES[self.current_mode]
        with open(self.log_file, "a") as f:
            f.write(f"{timestamp} - [{mode_name}] {round_time:.3f}s\n")

    def update_times_display(self):
        """Update the times display on screen for current mode."""
        recent_times = self.round_times[self.current_mode][-10:]
        for i, label in enumerate(self.times_labels):
            if i < len(recent_times):
                idx = len(recent_times) - 1 - i  # Reverse order (newest first)
                label.config(text=f"{i+1}. {recent_times[idx]:.3f}s")
            else:
                label.config(text="-")

    def on_resize(self, event):
        """Update window dimensions when resized."""
        if event.widget == self.root:
            self.window_width = event.width
            self.window_height = event.height

    def on_mouse_motion(self, event):
        """Track mouse motion for teleport modes."""
        if self.waiting_for_start:
            return

        # Use absolute coordinates relative to window (handles events from any widget)
        mouse_x = self.root.winfo_pointerx() - self.root.winfo_rootx()
        mouse_y = self.root.winfo_pointery() - self.root.winfo_rooty()

        if self.current_mode == MODE_TELEPORT_ZONE:
            # Check if mouse entered the target zone
            if self.current_zone:
                zone = self.current_zone
                if (
                    zone["x"] <= mouse_x <= zone["x"] + zone["width"]
                    and zone["y"] <= mouse_y <= zone["y"] + zone["height"]
                ):
                    self.on_zone_reached()

        elif self.current_mode == MODE_TELEPORT_TARGET:
            # Check if mouse entered the zone containing the target
            if self.current_zone:
                zone = self.current_zone
                if (
                    zone["x"] <= mouse_x <= zone["x"] + zone["width"]
                    and zone["y"] <= mouse_y <= zone["y"] + zone["height"]
                ):
                    self.on_zone_reached()

    def on_zone_reached(self):
        """Handle reaching the target zone in teleport modes."""
        self.current_clicks += 1
        self.progress_label.config(
            text=f"Progress: {self.current_clicks}/{self.clicks_per_round}"
        )

        # Clear zone highlight
        self.clear_zone_highlight()

        if self.current_clicks >= self.clicks_per_round:
            self.end_round()
        else:
            self.setup_next_target()

    def start_round(self, event=None):
        """Start a new round."""
        if not self.waiting_for_start:
            return

        self.waiting_for_start = False
        self.current_clicks = 0
        self.round_start_time = time.time()

        mode_name = MODE_NAMES[self.current_mode]
        self.status_label.config(text=f"GO! - {mode_name}")
        self.progress_label.config(text=f"Progress: 0/{self.clicks_per_round}")

        print(f"[ROUND] Starting round in mode: {mode_name}")

        self.setup_next_target()

    def setup_next_target(self):
        """Setup the next target based on current mode."""
        if self.current_mode == MODE_TELEPORT_ZONE:
            # Mode 1: Highlight one of 12 fixed zones (4 per screen)
            self.highlight_teleport_zone(show_zone=True, show_target=False)

        elif self.current_mode == MODE_TELEPORT_TARGET:
            # Mode 2: Show target, must teleport to its zone (12 zones)
            self.highlight_teleport_zone(show_zone=False, show_target=True)

        elif self.current_mode == MODE_CLICK_IN_ZONE:
            # Mode 3: Random zone, click anywhere inside
            self.highlight_random_click_zone()

        elif self.current_mode == MODE_CLICK_TARGET:
            # Mode 4: Small target anywhere, must click it
            self.place_click_target()

    def on_button_click(self, event=None):
        """Handle button click - for modes 3 and 4."""
        if self.waiting_for_start:
            return

        if self.current_mode not in [MODE_CLICK_IN_ZONE, MODE_CLICK_TARGET]:
            return  # Only handle clicks in click modes

        self.current_clicks += 1
        self.progress_label.config(
            text=f"Progress: {self.current_clicks}/{self.clicks_per_round}"
        )

        # Clear current zone and target
        self.clear_zone_highlight()
        self.canvas.place_forget()

        if self.current_clicks >= self.clicks_per_round:
            self.end_round()
        else:
            self.setup_next_target()

    def on_zone_click(self, event=None):
        """Handle click inside zone for mode 3."""
        if self.waiting_for_start:
            return

        if self.current_mode != MODE_CLICK_IN_ZONE:
            return

        # Check if click is within the current zone
        if self.current_zone:
            zone = self.current_zone
            # Get click position relative to window
            click_x = self.root.winfo_pointerx() - self.root.winfo_rootx()
            click_y = self.root.winfo_pointery() - self.root.winfo_rooty()

            if (
                zone["x"] <= click_x <= zone["x"] + zone["width"]
                and zone["y"] <= click_y <= zone["y"] + zone["height"]
            ):
                self.current_clicks += 1
                self.progress_label.config(
                    text=f"Progress: {self.current_clicks}/{self.clicks_per_round}"
                )
                self.clear_zone_highlight()

                if self.current_clicks >= self.clicks_per_round:
                    self.end_round()
                else:
                    self.setup_next_target()

    def highlight_teleport_zone(self, show_zone=True, show_target=False):
        """Highlight one of the 12 fixed teleport zones."""
        if not self.teleport_zones:
            return

        # Clear any existing highlight first
        if self.zone_highlight:
            self.main_canvas.delete(self.zone_highlight)
            self.zone_highlight = None
        self.target_canvas.place_forget()

        # Select a random zone from the 12 fixed zones
        self.current_zone = random.choice(self.teleport_zones)
        zone = self.current_zone

        margin = 5

        if show_zone:
            # Draw zone highlight on main canvas
            self.zone_highlight = self.main_canvas.create_rectangle(
                zone["x"] + margin,
                zone["y"] + margin,
                zone["x"] + zone["width"] - margin,
                zone["y"] + zone["height"] - margin,
                fill="#2E4A2E",  # Dark green background
                outline="#4CAF50",  # Green border
                width=3,
                tags="zone_highlight",
            )

            # Make sure UI elements stay on top
            self.main_canvas.lower(self.zone_highlight)

        if show_target:
            # Place target with crosshair somewhere in the zone
            # Account for crosshair size when positioning
            target_margin = self.crosshair_size + margin
            min_target_x = int(zone["x"] + target_margin)
            max_target_x = int(zone["x"] + zone["width"] - target_margin)
            min_target_y = int(zone["y"] + target_margin)
            max_target_y = int(zone["y"] + zone["height"] - target_margin)

            # Ensure valid range
            if max_target_x <= min_target_x:
                target_x = (min_target_x + max_target_x) // 2
            else:
                target_x = random.randint(min_target_x, max_target_x)

            if max_target_y <= min_target_y:
                target_y = (min_target_y + max_target_y) // 2
            else:
                target_y = random.randint(min_target_y, max_target_y)

            # Place canvas so that crosshair center is at target position
            self.target_canvas.place(
                x=target_x - self.crosshair_size, y=target_y - self.crosshair_size
            )
            print(
                f"[DEBUG] Target placed at ({target_x}, {target_y}) in zone {zone['screen']}"
            )

    def highlight_random_click_zone(self):
        """Create a random zone for click-in-zone mode (mode 3)."""
        # Clear any existing highlight first
        if self.zone_highlight:
            self.main_canvas.delete(self.zone_highlight)
            self.zone_highlight = None
        self.target_canvas.place_forget()

        # Generate random zone size
        min_size = 150
        max_size = 400
        zone_width = random.randint(min_size, max_size)
        zone_height = random.randint(min_size, max_size)

        # Pick a random screen region
        region = random.choice(self.screen_regions)

        # Random position within the screen (with margins for UI)
        margin = 50
        ui_top_margin = 150
        ui_side_margin = 220

        max_x = region["x"] + region["width"] - zone_width - ui_side_margin
        max_y = region["y"] + region["height"] - zone_height - margin
        min_x = region["x"] + ui_side_margin
        min_y = region["y"] + ui_top_margin

        if max_x <= min_x:
            max_x = min_x + 1
        if max_y <= min_y:
            max_y = min_y + 1

        zone_x = random.randint(int(min_x), int(max_x))
        zone_y = random.randint(int(min_y), int(max_y))

        self.current_zone = {
            "x": zone_x,
            "y": zone_y,
            "width": zone_width,
            "height": zone_height,
        }
        zone = self.current_zone

        # Draw zone highlight
        self.zone_highlight = self.main_canvas.create_rectangle(
            zone["x"],
            zone["y"],
            zone["x"] + zone["width"],
            zone["y"] + zone["height"],
            fill="#2E3A4A",  # Dark blue background
            outline="#6699CC",  # Blue border
            width=3,
            tags="zone_highlight",
        )

        # Make sure UI elements stay on top
        self.main_canvas.lower(self.zone_highlight)

    def place_click_target(self):
        """Place a small target button anywhere for mode 4."""
        # Clear any existing highlight
        if self.zone_highlight:
            self.main_canvas.delete(self.zone_highlight)
            self.zone_highlight = None
        self.target_canvas.place_forget()
        self.current_zone = None

        # Use the existing move_button_random logic but with smaller target
        self.move_target_random()

    def move_target_random(self):
        """Move the target with crosshair to a random position."""
        # Account for crosshair size
        target_size = self.crosshair_size * 2
        ui_top_margin = 150
        ui_side_margin = 220

        valid_positions = []

        for region in self.screen_regions:
            min_x = region["x"] + ui_side_margin + self.crosshair_size
            min_y = region["y"] + ui_top_margin + self.crosshair_size
            max_x = region["x"] + region["width"] - ui_side_margin - self.crosshair_size
            max_y = region["y"] + region["height"] - self.crosshair_size - 50

            if max_x > min_x and max_y > min_y:
                valid_positions.append(
                    {
                        "min_x": min_x,
                        "max_x": max_x,
                        "min_y": min_y,
                        "max_y": max_y,
                        "weight": (max_x - min_x) * (max_y - min_y),
                        "region": region["name"],
                    }
                )

        if not valid_positions:
            region = (
                self.screen_regions[0]
                if self.screen_regions
                else {"x": 0, "y": 0, "width": 800, "height": 600}
            )
            new_x = region["x"] + region["width"] // 2
            new_y = region["y"] + region["height"] // 2
        else:
            total_weight = sum(p["weight"] for p in valid_positions)
            r = random.uniform(0, total_weight)
            cumulative = 0
            selected = valid_positions[0]
            for pos in valid_positions:
                cumulative += pos["weight"]
                if r <= cumulative:
                    selected = pos
                    break

            new_x = random.randint(int(selected["min_x"]), int(selected["max_x"]))
            new_y = random.randint(int(selected["min_y"]), int(selected["max_y"]))
            print(
                f"[DEBUG] Mode 4 target at ({new_x}, {new_y}) in region {selected['region']}"
            )

        # Place canvas so crosshair center is at target position
        self.target_canvas.place(
            x=new_x - self.crosshair_size, y=new_y - self.crosshair_size
        )

    def highlight_random_zone(self, show_zone=True, show_target=False):
        """Highlight a random teleport zone and/or show target."""
        if not self.teleport_zones:
            return

        # Clear any existing highlight first
        if self.zone_highlight:
            self.main_canvas.delete(self.zone_highlight)
            self.zone_highlight = None
        self.target_canvas.place_forget()

        # Select a random zone
        self.current_zone = random.choice(self.teleport_zones)
        zone = self.current_zone

        margin = 5

        if show_zone:
            # Draw zone highlight on main canvas
            self.zone_highlight = self.main_canvas.create_rectangle(
                zone["x"] + margin,
                zone["y"] + margin,
                zone["x"] + zone["width"] - margin,
                zone["y"] + zone["height"] - margin,
                fill="#2E4A2E",  # Dark green background
                outline="#4CAF50",  # Green border
                width=3,
                tags="zone_highlight",
            )

            # Make sure UI elements stay on top
            self.main_canvas.lower(self.zone_highlight)

        if show_target:
            # Place target with crosshair somewhere in the zone
            target_margin = self.crosshair_size + margin
            min_target_x = int(zone["x"] + target_margin)
            max_target_x = int(zone["x"] + zone["width"] - target_margin)
            min_target_y = int(zone["y"] + target_margin)
            max_target_y = int(zone["y"] + zone["height"] - target_margin)

            if max_target_x <= min_target_x:
                target_x = (min_target_x + max_target_x) // 2
            else:
                target_x = random.randint(min_target_x, max_target_x)

            if max_target_y <= min_target_y:
                target_y = (min_target_y + max_target_y) // 2
            else:
                target_y = random.randint(min_target_y, max_target_y)

            self.target_canvas.place(
                x=target_x - self.crosshair_size, y=target_y - self.crosshair_size
            )

    def clear_zone_highlight(self):
        """Clear the current zone highlight."""
        if self.zone_highlight:
            self.main_canvas.delete(self.zone_highlight)
            self.zone_highlight = None
        self.target_canvas.place_forget()
        self.current_zone = None

    def end_round(self):
        """End the current round and show results."""
        round_time = time.time() - self.round_start_time
        self.round_times[self.current_mode].append(round_time)
        self.log_round_time(round_time)

        self.waiting_for_start = True
        self.canvas.place_forget()
        self.clear_zone_highlight()

        mode_name = MODE_NAMES[self.current_mode]
        self.status_label.config(
            text=f"Round complete! Time: {round_time:.3f}s - Press SPACE for next round"
        )
        self.update_times_display()

        print(f"[ROUND] Completed - Mode: {mode_name}, Time: {round_time:.3f}s")

    def move_button_random(self):
        """Move the button to a random position within valid screen regions."""
        margin = 20
        button_size = self.button_radius * 2
        ui_top_margin = 120  # Space for top UI elements
        ui_right_margin = 200  # Space for times panel

        # Collect all valid spawn points from actual screen regions
        valid_positions = []

        for region in self.screen_regions:
            # Calculate valid bounds within this screen region
            min_x = region["x"] + margin
            min_y = region["y"] + max(margin, ui_top_margin)  # Account for top UI
            max_x = region["x"] + region["width"] - button_size - margin
            max_y = region["y"] + region["height"] - button_size - margin

            # For the rightmost part of the rightmost screen, account for times panel
            # Check if this region extends to the right edge of all screens
            region_right_edge = region["x"] + region["width"]
            total_right_edge = max(r["x"] + r["width"] for r in self.screen_regions)
            if (
                region_right_edge >= total_right_edge - 10
            ):  # This region is at the right edge
                max_x = max_x - ui_right_margin

            if max_x > min_x and max_y > min_y:
                valid_positions.append(
                    {
                        "min_x": min_x,
                        "max_x": max_x,
                        "min_y": min_y,
                        "max_y": max_y,
                        "weight": (max_x - min_x)
                        * (max_y - min_y),  # Area-based weight
                    }
                )

        if not valid_positions:
            # Fallback: use center of first screen region
            region = (
                self.screen_regions[0]
                if self.screen_regions
                else {"x": 0, "y": 0, "width": 800, "height": 600}
            )
            new_x = region["x"] + region["width"] // 2 - self.button_radius
            new_y = region["y"] + region["height"] // 2 - self.button_radius
        else:
            # Weight selection by screen area for fair distribution
            total_weight = sum(p["weight"] for p in valid_positions)
            r = random.uniform(0, total_weight)
            cumulative = 0
            selected = valid_positions[0]
            for pos in valid_positions:
                cumulative += pos["weight"]
                if r <= cumulative:
                    selected = pos
                    break

            new_x = random.randint(int(selected["min_x"]), int(selected["max_x"]))
            new_y = random.randint(int(selected["min_y"]), int(selected["max_y"]))

        self.canvas.place(x=new_x, y=new_y)

    def run(self):
        """Start the application."""
        self.root.mainloop()


if __name__ == "__main__":
    trainer = MouseTrainer()
    trainer.run()
