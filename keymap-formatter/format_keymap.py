#!/usr/bin/env python3
"""
ZMK Keymap Formatter for Hillside46

Formats layer bindings into a visual grid that matches the physical keyboard layout.
Usage: python format_keymap.py [keymap_file] [-i/--in-place]
"""

import re
import sys
from pathlib import Path

# Layout configuration for Hillside46
CONFIG = {
    "cell_width": 20,
    "split_gap": 91,  # space between left and right halves (was 96, corrected)
    "thumb_gap": 4,
}

# Box-drawing characters
BOX = {
    "h": "─",
    "v": "│",
    "tl": "╭",
    "tr": "╮",
    "bl": "╰",
    "br": "╯",
    "t": "┬",
    "b": "┴",
    "l": "├",
    "r": "┤",
    "x": "┼",
}


def pad_binding(binding: str, width: int) -> str:
    """Pad a binding to exactly `width` characters."""
    if len(binding) >= width:
        return binding + " "
    return binding.ljust(width)


def make_separator(count: int, style: str = "mid", width: int = 20) -> str:
    """Create a separator line for `count` cells."""
    h = BOX["h"]
    cell = h * (width - 1)

    if style == "top":
        left, mid, right = BOX["tl"], BOX["t"], BOX["tr"]
    elif style == "bottom":
        left, mid, right = BOX["bl"], BOX["b"], BOX["br"]
    else:
        left, mid, right = BOX["l"], BOX["x"], BOX["r"]

    return left + mid.join([cell] * count) + right


def merge_box_chars(existing: str, new: str) -> str:
    """Merge two box-drawing characters at the same position."""
    if existing == " ":
        return new
    if existing == new:
        return existing

    h = BOX["h"]
    tl, tr, bl, br = BOX["tl"], BOX["tr"], BOX["bl"], BOX["br"]
    t, b, l, r, x = BOX["t"], BOX["b"], BOX["l"], BOX["r"], BOX["x"]

    rules = {
        (h, h): h,
        (b, t): x,
        (t, b): x,
        (br, tl): r,
        (tl, br): r,
        (bl, tr): l,
        (tr, bl): l,
        (h, tl): t,
        (tl, h): t,
        (h, tr): t,
        (tr, h): t,
        (h, bl): b,
        (bl, h): b,
        (h, br): b,
        (br, h): b,
        (h, t): t,
        (t, h): t,
        (h, b): b,
        (b, h): b,
        (b, tl): x,
        (tl, b): x,
        (b, tr): x,
        (tr, b): x,
        (t, bl): x,
        (bl, t): x,
        (t, br): x,
        (br, t): x,
        (tr, t): t,
        (t, tr): t,
        (tl, t): t,
        (t, tl): t,
        (tr, h): tr,
        (tl, h): tl,
        (br, h): br,
        (bl, h): bl,
        # Corner + horizontal = T-junction (direction-agnostic)
        (br, h): b,
        (bl, h): b,
        (tr, h): t,
        (tl, h): t,
    }
    return rules.get((existing, new), new)


def format_layer(bindings: list[str], layer_name: str = "") -> list[str]:
    """Format 46 bindings into a visual grid matching the Hillside46 layout."""
    if len(bindings) != 46:
        raise ValueError(f"Expected 46 bindings, got {len(bindings)}")

    cw = CONFIG["cell_width"]
    split_gap = " " * CONFIG["split_gap"]
    thumb_gap = " " * CONFIG["thumb_gap"]

    # Pre-compute separators
    sep6_top = make_separator(6, "top", cw)
    sep6_mid = make_separator(6, "mid", cw)
    sep6_bot = make_separator(6, "bottom", cw)
    sep1_top = make_separator(1, "top", cw)
    sep1_bot = make_separator(1, "bottom", cw)
    sep4_top = make_separator(4, "top", cw)
    sep4_bot = make_separator(4, "bottom", cw)

    # Calculate gaps
    middle_gap_size = CONFIG["split_gap"] - cw * 2 - CONFIG["thumb_gap"] * 2
    middle_gap = " " * middle_gap_size
    thumb_indent_size = cw * 4 + CONFIG["thumb_gap"]
    thumb_indent = " " * thumb_indent_size
    thumb_split_size = CONFIG["split_gap"] - cw * 4 - CONFIG["thumb_gap"] * 2 + 1
    thumb_split = " " * thumb_split_size
    spaces_to_thumb = CONFIG["thumb_gap"] - 1

    # Keys gap is 1 more than split_gap because "    " prefix is 1 char longer than "// "
    keys_gap = " " * (CONFIG["split_gap"] + 1)

    def format_keys(keys: list[str]) -> str:
        return "".join(pad_binding(k, cw) for k in keys)

    lines = []

    # Row 0 (keys 0-5, 6-11)
    left = format_keys(bindings[0:6])
    right = format_keys(bindings[6:12])
    lines.append(f"// {sep6_top}{split_gap}{sep6_top}")
    lines.append(f"    {left}{keys_gap}{right}")

    # Row 1 (keys 12-17, 18-23)
    left = format_keys(bindings[12:18])
    right = format_keys(bindings[18:24])
    lines.append(f"// {sep6_mid}{split_gap}{sep6_mid}")
    lines.append(f"    {left}{keys_gap}{right}")

    # Row 2 (keys 24-29 + thumb 30, thumb 31 + keys 32-37)
    left = format_keys(bindings[24:30])
    right = format_keys(bindings[32:38])
    thumb_30 = pad_binding(bindings[30], cw)
    thumb_31 = pad_binding(bindings[31], cw)

    lines.append(
        f"// {sep6_mid}{' ' * spaces_to_thumb}{sep1_top}{middle_gap}{sep1_top}{' ' * spaces_to_thumb}{sep6_mid}"
    )
    lines.append(
        f"    {left}{thumb_gap}{thumb_30}{middle_gap} {thumb_31}{thumb_gap}{right}"
    )

    # Merged line: sep6_bot + sep4_top overlaid
    # Total width is same as other separator lines: 336
    total_width = 336
    merged = [" "] * total_width
    merged[0:3] = list("// ")

    # Layer 1: Left sep6_bot (positions 3-123)
    for i, c in enumerate(sep6_bot):
        merged[3 + i] = c

    # Layer 2: Right sep6_bot
    # Right main grid starts at: total_width - 121 = 215
    # (since we need 121 chars for sep6_bot ending at position 335)
    right_main_start = total_width - len(sep6_bot)
    for i, c in enumerate(sep6_bot):
        merged[right_main_start + i] = c

    # Layer 3: Left sep1_bot (for single key [30], starts at 127)
    for i, c in enumerate(sep1_bot):
        pos = 127 + i
        if pos < total_width:
            merged[pos] = merge_box_chars(merged[pos], c)

    # Layer 4: Right sep1_bot (for single key [31], starts at 191)
    for i, c in enumerate(sep1_bot):
        pos = 191 + i
        if pos < total_width:
            merged[pos] = merge_box_chars(merged[pos], c)

    # Layer 5: Left sep4_top (thumb row)
    # First ┬ should be at position 87, so ╭ would be at 87-4=83
    # But we overlay on main's ─, so actual start is 84 for ╭ (which becomes ┬)
    # thumb_indent_size = 4*20 + 4 = 84
    left_thumb_start = 3 + thumb_indent_size
    for i, c in enumerate(sep4_top):
        pos = left_thumb_start + i
        if pos < total_width:
            merged[pos] = merge_box_chars(merged[pos], c)

    # Layer 6: Right sep4_top
    # Right thumb ends where ╮ is at position 167 (mirrored: ╭ at 171)
    # Gap between thumbs is 3 chars (168-170)
    # Right thumb starts at 171
    right_thumb_start = 171
    for i, c in enumerate(sep4_top):
        pos = right_thumb_start + i
        if pos < total_width:
            merged[pos] = merge_box_chars(merged[pos], c)

    lines.append("".join(merged).rstrip())

    # Thumb keys row
    left_thumbs = format_keys(bindings[38:42])
    right_thumbs = format_keys(bindings[42:46])
    thumb_keys_gap = " " * 4  # Gap between left and right thumb keys
    lines.append(f"    {thumb_indent}{left_thumbs}{thumb_keys_gap}{right_thumbs}")

    # Thumb row bottom
    thumb_sep_gap = (
        " " * 3
    )  # Gap between left and right thumb separators (1 less due to // vs spaces)
    lines.append(f"// {thumb_indent}{sep4_bot}{thumb_sep_gap}{sep4_bot}")

    return lines


def parse_bindings(bindings_str: str) -> list[str]:
    """Parse a bindings string into a list of individual bindings."""
    bindings_str = re.sub(r"//.*$", "", bindings_str, flags=re.MULTILINE)
    tokens = bindings_str.split()
    bindings = []
    current = None

    for token in tokens:
        if token.startswith("&"):
            if current:
                bindings.append(current)
            current = token
        elif current:
            current += " " + token

    if current:
        bindings.append(current)

    return bindings


def extract_and_format_layers(content: str) -> str:
    """Find all layer bindings and format them."""
    pattern = re.compile(r"(bindings\s*=\s*<)(.*?)(>\s*;)", re.DOTALL)

    def replace(match):
        bindings_str = match.group(2)
        try:
            bindings = parse_bindings(bindings_str)
            if len(bindings) == 46:
                formatted = "\n".join(format_layer(bindings))
                return f"bindings = <\n{formatted}\n    >;"
            return match.group(0)
        except Exception as e:
            print(f"Warning: {e}", file=sys.stderr)
            return match.group(0)

    return pattern.sub(replace, content)


def main():
    if len(sys.argv) < 2:
        keymap_path = Path(__file__).parent.parent / "config" / "hillside46.keymap"
    else:
        keymap_path = Path(sys.argv[1])

    if not keymap_path.exists():
        print(f"Error: {keymap_path} not found", file=sys.stderr)
        sys.exit(1)

    content = keymap_path.read_text()
    formatted = extract_and_format_layers(content)

    if "--in-place" in sys.argv or "-i" in sys.argv:
        keymap_path.write_text(formatted)
        print(f"Formatted {keymap_path}", file=sys.stderr)
    else:
        print(formatted)


if __name__ == "__main__":
    main()
