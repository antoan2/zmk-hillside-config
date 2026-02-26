#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

TARGET_BOARDS = ("hillside46", "ferris_rev02")

# Opinionated combo display layout:
# - key = virtual layer name
# - value = list of combo labels (the combo "k" value in generated YAML)
# Any combo not listed here is kept on the base layer (i.e. no forced virtual layer).
COMBOS_BY_DISPLAY_LAYER = {
    "Combos/Symbols": [
        "~",
        "@",
        "#",
        "$",
        "%",
        "^",
        "&",
        "*",
        "?",
        "!",
        "_",
        "+",
        "-",
        "=",
        "(",
        ")",
        "[",
        "}",
        "{",
        "]",
        "()",
        "[]",
        "{}",
        "'",
        '"',
        "`",
        "<",
        ">",
        "|",
        "\\",
        "/",
        ":",
        ";",
    ],
    "Combos/Edit": [
        "↹",
        "ENTER",
        "Ctl+ENTER",
        "Esc",
        "Cut",
        "Copy",
        "Paste",
        "Plain Paste",
        ":w",
        ":wq",
    ],
}


def ensure_pyyaml():
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "PyYAML is required. Install with: pip install pyyaml"
        ) from exc
    return yaml


def run(cmd: list[str], *, capture: bool = False) -> str | None:
    try:
        if capture:
            result = subprocess.run(cmd, check=True, text=True, capture_output=True)
            return result.stdout
        subprocess.run(cmd, check=True)
        return None
    except subprocess.CalledProcessError as exc:
        print("[ERROR] Command failed:")
        print(f"  {' '.join(cmd)}")
        if exc.stdout:
            print("[ERROR] stdout:")
            print(exc.stdout.rstrip())
        if exc.stderr:
            print("[ERROR] stderr:")
            print(exc.stderr.rstrip())
        raise SystemExit(exc.returncode)


def build_combo_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    duplicates: set[str] = set()
    for layer_name, combo_labels in COMBOS_BY_DISPLAY_LAYER.items():
        for label in combo_labels:
            norm = str(label).strip()
            if norm in lookup and lookup[norm] != layer_name:
                duplicates.add(norm)
            lookup[norm] = layer_name

    if duplicates:
        print("[WARN] Duplicate combo labels assigned to multiple virtual layers:")
        for label in sorted(duplicates):
            print(f"  - {label}")
    return lookup


def find_keymap_cli() -> list[str]:
    # Prefer the keymap executable from the *active Python environment*.
    env_keymap = Path(sys.executable).parent / "keymap"
    if env_keymap.exists():
        print(f"[INFO] Using keymap CLI from Python env: {env_keymap}")
        return [str(env_keymap)]

    # Fallback to PATH lookup.
    keymap_bin = shutil.which("keymap")
    if keymap_bin:
        return [keymap_bin]

    raise SystemExit(
        "[ERROR] 'keymap' command not found in PATH.\n"
        "Install keymap-drawer in the active environment, then retry."
    )


def transform_yaml(yaml_path: Path, yaml_module, combo_lookup: dict[str, str]) -> None:
    data = yaml_module.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    combos = data.get("combos", []) or []
    if not isinstance(combos, list):
        combos = []

    unmatched: list[str] = []
    matched_count = 0

    for combo in combos:
        if not isinstance(combo, dict):
            continue

        label = str(combo.get("k", "")).strip()
        layer_name = combo_lookup.get(label)
        if layer_name:
            combo["l"] = [layer_name]
            matched_count += 1
        else:
            # Keep on base layer by default.
            combo.pop("l", None)
            if label:
                unmatched.append(label)

    yaml_path.write_text(
        yaml_module.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    unique_unmatched = sorted(set(unmatched))
    print(
        f"[INFO] {yaml_path.name}: {matched_count}/{len(combos)} combos mapped to virtual layers"
    )
    if unique_unmatched:
        print(f"[WARN] {yaml_path.name}: combos left on base layer (not matched):")
        for label in unique_unmatched:
            print(f"  - {label}")


def draw_one(
    root: Path,
    board: str,
    yaml_module,
    combo_lookup: dict[str, str],
    keymap_cli: list[str],
) -> None:
    config_file = root / "keymap-drawer" / "config.yaml"
    out_dir = root / "keymap-drawer"
    keymap_file = root / "config" / f"{board}.keymap"
    yaml_file = out_dir / f"{board}.yaml"
    svg_file = out_dir / f"{board}.svg"

    if not keymap_file.exists():
        print(f"Skipping {board}: {keymap_file} not found")
        return

    virtual_layers = list(COMBOS_BY_DISPLAY_LAYER.keys())
    print(f"[INFO] Parsing {board} with virtual layers: {', '.join(virtual_layers)}")

    parsed = run(
        keymap_cli
        + [
            "-c",
            str(config_file),
            "parse",
            "-c",
            "10",
            "-z",
            str(keymap_file),
            "--virtual-layers",
        ]
        + virtual_layers,
        capture=True,
    )
    yaml_file.write_text(parsed or "", encoding="utf-8")

    transform_yaml(yaml_file, yaml_module, combo_lookup)

    drawn = run(
        keymap_cli
        + [
            "-c",
            str(config_file),
            "draw",
            str(yaml_file),
        ],
        capture=True,
    )
    svg_file.write_text(drawn or "", encoding="utf-8")
    print(f"[OK] Generated {svg_file}")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    config_file = root / "keymap-drawer" / "config.yaml"
    if not config_file.exists():
        print(f"Missing keymap drawer config: {config_file}", file=sys.stderr)
        return 1

    yaml_module = ensure_pyyaml()
    combo_lookup = build_combo_lookup()
    keymap_cli = find_keymap_cli()

    print(
        "[INFO] Running opinionated draw (no args): all boards, grouped virtual layers"
    )
    for board in TARGET_BOARDS:
        draw_one(root, board, yaml_module, combo_lookup, keymap_cli)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
