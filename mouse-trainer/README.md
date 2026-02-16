# Mouse Trainer

A Python-based tool to practice quick mouse movements and teleportation, designed to work with ZMK keyboard firmware's pointer teleport feature.

## Overview

Mouse Trainer provides four training modes to help you build muscle memory for efficient mouse movements:

1. **Teleport to Zone** - Teleport to one of 12 highlighted zones (4 per screen)
2. **Teleport to Target** - Target appears, teleport to its zone (12 zones)
3. **Click in Zone** - Random zone appears, click inside it
4. **Click Target** - Small target appears anywhere, click it precisely

### Multi-Monitor Support

The application supports multi-monitor setups with offsets, spawning a window covering all screens but only placing targets within actual screen boundaries.

## Requirements

- Python 3.10+
- Tkinter (system package, not installable via pip)
- `screeninfo` (for multi-monitor support)
- `uv` (recommended for dependency management)

## Installation

### System Dependencies

Tkinter must be installed via your system's package manager:

```bash
# Ubuntu/Debian
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

### Using uv (recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (uses system Python for tkinter support)
make install
```

### Using pip (alternative)

```bash
pip install screeninfo ruff
```

## Usage

### Running the Application

```bash
# Using make
make run

# Using uv directly
uv run python mouse_trainer.py

# Using python directly
python mouse_trainer.py
```

### Keyboard Controls

| Key         | Action                            |
| ----------- | --------------------------------- |
| `ESC` / `Q` | Quit the application              |
| `Space`     | Start a round                     |
| `S`         | Open settings                     |
| `1`         | Switch to Teleport to Zone mode   |
| `2`         | Switch to Teleport to Target mode |
| `3`         | Switch to Click in Zone mode      |
| `4`         | Switch to Click Target mode       |
| `F11`       | Toggle fullscreen                 |

### Training Modes

#### Mode 1: Teleport to Zone
Practice teleporting your mouse cursor to specific zones on the screen. The screen is divided into 12 zones (4 per monitor in a 3-monitor setup, or 4 zones for single monitor).

#### Mode 2: Teleport to Target
A target appears in a random zone. Teleport to the zone containing the target.

#### Mode 3: Click in Zone
A random zone is highlighted. Click anywhere inside that zone.

#### Mode 4: Click Target
A small target button appears at a random position. Click it precisely.

## Development

### Project Structure

```
mouse-trainer/
├── mouse_trainer.py    # Main application
├── pyproject.toml      # Project configuration (uv/pip)
├── Makefile            # Development commands
├── README.md           # This file
└── round_times.log     # Performance log (generated)
```

### Development Commands

```bash
# Install dependencies
make install

# Run the application
make run

# Lint code with ruff
make lint

# Format code with ruff
make format

# Run both lint and format checks
make check

# Clean generated files
make clean
```

### Code Style

This project uses [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

- Line length: 88 characters
- Python version: 3.10+
- Follows PEP 8 with reasonable exceptions

### Adding New Features

When implementing new features:

1. Follow the existing code structure and patterns
2. Use type hints where practical
3. Add docstrings to new functions and classes
4. Run `make check` before committing

## Configuration

### Settings Dialog

Press `S` to open the settings dialog where you can configure:
- Number of targets per round (1-100)

### Performance Logging

Round times are automatically logged to `round_times.log` for tracking progress over time.

## Integration with ZMK

This trainer is designed to work with ZMK keyboard firmware's pointer teleport feature (`zmk_pointer`). The 12 zones correspond to teleport positions that can be configured in your ZMK keymap.

## License

MIT License - See LICENSE file for details.
