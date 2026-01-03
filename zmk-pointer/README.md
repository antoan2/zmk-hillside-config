# ZMK Daemon-Controlled Mouse Layer

A Python daemon for Ubuntu/Wayland that provides keyboard-driven cursor control
via signal interception. The ZMK keyboard sends modifier combinations
(`LCtrl+RCtrl + key`) as signals, and this daemon interprets them to control
the cursor.

## Architecture

```
┌─────────────────┐      ┌─────────────────┐
│  ZMK Keyboard   │ ──── │  Python Daemon  │
│  Sends signals  │      │  Moves cursor   │
│  (LCtrl+RCtrl+X)│      │  Teleports      │
└─────────────────┘      └─────────────────┘
```

## Features

- **Movement**: WASD keys with acceleration and inertia
- **Precision Mode**: Slower, more precise movement (TFGH signals)
- **Scroll Mode**: WASD becomes scroll (YUNJ signals)
- **Teleportation**: F13-F24 for 12 grid positions across 3 screens
- **Native Clicks**: Mouse buttons handled directly by ZMK (lowest latency)

## Requirements

- Ubuntu 24.04+ with Wayland
- Python 3.10+
- Root access or membership in `input` group

## Installation

### 1. Install Python Dependencies

```bash
pip install evdev screeninfo --break-system-packages
```

### 2. Enable uinput Kernel Module

```bash
# Load the module
sudo modprobe uinput

# Make it persistent across reboots
echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf
```

### 3. Set Up Permissions

**Option A: Run as root** (simplest)
```bash
sudo python zmk_pointer.py
```

**Option B: Add udev rule** (recommended for regular use)
```bash
# Create udev rule for uinput access
echo 'KERNEL=="uinput", MODE="0660", GROUP="input"' | \
    sudo tee /etc/udev/rules.d/99-uinput.rules

# Add yourself to the input group
sudo usermod -aG input $USER

# Reload udev rules
sudo udevadm control --reload-rules

# Log out and back in for group membership to take effect
```

## Usage

```bash
cd zmk-pointer
python zmk_pointer.py
# or
sudo python zmk_pointer.py
```

### Command Line Options

```bash
python zmk_pointer.py --list          # List available keyboards
python zmk_pointer.py --device 0      # Use keyboard at index 0
python zmk_pointer.py --grab          # Grab keyboard exclusively
python zmk_pointer.py --no-debug      # Disable debug output
```

## Controls

### Activation

Hold **LCtrl + RCtrl** together to activate pointer mode. All signals require
this modifier combination.

### Movement (Left Hand - WASD)

```
       ┌───┐
       │ W │  ↑ Up
   ┌───┼───┼───┐
   │ A │   │ D │  ← Left / Right →
   └───┼───┼───┘
       │ S │  ↓ Down
       └───┘
```

Movement keys support:
- Velocity ramping (starts slow, accelerates)
- Diagonal movement (45° interpolation)
- Inertia (smooth deceleration when released)

### Precision Mode (TFGH)

Hold **left inner thumb** to activate precision mode. Movement is slower and
more precise, using TFGH signal keys instead of WASD.

### Scroll Mode (YUNJ)

Hold **G key** or **right outer thumb** to activate scroll mode. WASD becomes
scroll directions using YUNJ signal keys.

### Teleportation Grid (F13-F24)

12 positions across 3 screens (2×2 grid per screen):

```
Screen 1        Screen 2        Screen 3
┌─────┬─────┐  ┌─────┬─────┐  ┌─────┬─────┐
│ F13 │ F14 │  │ F17 │ F18 │  │ F21 │ F22 │  ← Top row
├─────┼─────┤  ├─────┼─────┤  ├─────┼─────┤
│ F15 │ F16 │  │ F19 │ F20 │  │ F23 │ F24 │  ← Bottom row
└─────┴─────┘  └─────┴─────┘  └─────┴─────┘
```

On the keyboard, teleport keys are mapped to the right hand top and home rows.

### Mouse Clicks (Native ZMK)

Clicks are handled directly by ZMK for lowest latency:
- **Left thumb**: Left Click
- **Right thumb**: Right Click
- **Encoder press / extra thumb**: Middle Click

## Signal Protocol

| Mode | Signal Pattern | Keys |
|------|----------------|------|
| Movement (normal) | `LCtrl + RCtrl + [key]` | W, A, S, D |
| Movement (precision) | `LCtrl + RCtrl + [key]` | T, F, G, H |
| Scroll | `LCtrl + RCtrl + [key]` | Y, U, N, J |
| Teleport | `LCtrl + RCtrl + [key]` | F13-F24 |

## Layer Structure

```
BASE ──[toggle bottom-left]──► MOUSE
                                  │
                   ┌──────────────┼──────────────┐
                   ▼              ▼              ▼
               PRECISION      SCROLL         (normal)
              (left thumb)   (G or thumb)
```

## Troubleshooting

### Daemon not receiving signals

1. Make sure the daemon is running with appropriate permissions
2. Check that your ZMK firmware includes the mouse.dtsi macros
3. Verify the keyboard is detected: `python zmk_pointer.py --list`

### Teleport not reaching all screens

The daemon auto-detects monitors using `screeninfo`. Ensure all monitors are
detected: the startup info will show detected screens and their positions.

### Movement feels laggy

- The daemon adds ~1-5ms latency vs native ZMK mouse
- For lowest latency on clicks, they remain native ZMK (`&mkp`)
- Try running with `--no-debug` to reduce output overhead

## Speed Profiles

| Mode   | Base Speed   | Max Speed     | Ramp Time |
| ------ | ------------ | ------------- | --------- |
| Normal | 3 px/update  | 20 px/update  | 0.5s      |
| Fast   | 30 px/update | 150 px/update | 0.3s      |

Movement starts at base speed and accelerates to max speed over the ramp time using cubic ease-out.

## Debug Output

The script outputs key events to the terminal:

```
[12:00:01] Key: u → Teleport (720, 270)
[12:00:02] Key: j → Pointer Left normal (active: {'j'})
[12:00:02] Key: j release (active: {})
[12:00:03] Key: lctrl → Fast mode ON
[12:00:03] Key: ; → Pointer Right FAST (active: {';'})
[12:00:04] Key: lctrl release → Fast mode OFF
```

## Troubleshooting

### "No keyboard found"
- Make sure you have a keyboard connected
- Check that you have permission to read `/dev/input/event*` devices

### "Permission denied" errors
- Run with `sudo`, or
- Ensure your user is in the `input` group and you've logged out/in
- Check that the uinput module is loaded: `lsmod | grep uinput`

### Cursor doesn't move
- Verify the virtual device was created: `ls /dev/input/by-id/ | grep ZMK`
- Check if your Wayland compositor supports uinput devices

### Wrong screen bounds
- If you have multiple monitors, ensure they're configured correctly
- The script spans all connected monitors

## License

MIT
