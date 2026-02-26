# Here is my layout

Inspirations
- Home row mods
  - https://precondition.github.io/home-row-mods
  - https://github.com/urob/zmk-config?tab=readme-ov-file#timeless-homerow-mods
  - https://sunaku.github.io/home-row-mods.html#porting-to-zmk
  - https://github.com/gagbo/zmk-config-corne/blob/main/config/sunaku_hrm.dtsi
- Implement the qwerty-lafayette for special chars (with added dead keys)

This is currently almost the same as my ferris sweep layout.


# Hillside 46
![Layout](./keymap-drawer/hillside46.svg)
# Ferris
![Layout](./keymap-drawer/ferris_rev02.svg)

---

# Local build (Linux)

This repo now includes local helpers:

- Setup local west workspace: `make zmk-setup`
- Build left half UF2: `make zmk-left`
- Build right half UF2: `make zmk-right`
- Build settings reset UF2: `make zmk-reset`

Output UF2 files are generated under:

- `.zmk/build/left/zephyr/zmk.uf2`
- `.zmk/build/right/zephyr/zmk.uf2`
- `.zmk/build/reset/zephyr/zmk.uf2`

Note: [config/west.yml](config/west.yml) tracks ZMK `main`, so upstream ZMK/Zephyr changes are pulled over time. For maximum stability, pin that revision to a tag/commit before long-term use.

---

# Special layer

The special layer follows the qwerty-lafayette idea for French special characters. It is activated on the base layer with the `io` combo, which triggers a one-shot special layer via `&sl` (through a macro). After one keypress, it automatically returns to base. The `q` position on this layer is mapped to `éé` for quick insertion.

# Daemon-Controlled Mouse Layer

The mouse layer uses a host-side Python daemon (`zmk-pointer/zmk_pointer.py`) that intercepts keyboard signals to control the cursor. The keyboard sends modifier+F-key combinations as signals.

## Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  ZMK Keyboard   │ ───► │  Python Daemon  │ ───► │  Virtual Mouse  │
│  (mouse.dtsi)   │      │  (zmk_pointer)  │      │  (uinput)       │
└─────────────────┘      └─────────────────┘      └─────────────────┘
     Sends:                  Interprets:              Outputs:
  Ctrl+Shift+F13-24         F13-16 = move           Cursor movement
  Ctrl+Shift+Alt+F13-24     F17-20 = precision      Teleportation
                            F21-24 = scroll
```

## Signal Protocol

| Action        | Modifiers        | Keys    | Description                  |
| ------------- | ---------------- | ------- | ---------------------------- |
| **Movement**  | `Ctrl+Shift`     | F13-F16 | Normal speed cursor movement |
| **Precision** | `Ctrl+Shift`     | F17-F20 | Slow/precise cursor movement |
| **Scroll**    | `Ctrl+Shift`     | F21-F24 | Scroll wheel emulation       |
| **Teleport**  | `Ctrl+Shift+Alt` | F13-F24 | Jump to screen grid position |

### Key Mapping

```
Movement (F13-F16):     Precision (F17-F20):    Scroll (F21-F24):
    F13 (↑)                 F17 (↑)                 F21 (↑)
F15 (←) F16 (→)         F19 (←) F20 (→)         F23 (←) F24 (→)
    F14 (↓)                 F18 (↓)                 F22 (↓)
```

### Teleport Grid (12 positions across 3 screens)

```
Screen 1        Screen 2        Screen 3
┌─────┬─────┐  ┌─────┬─────┐  ┌─────┬─────┐
│ F13 │ F14 │  │ F17 │ F18 │  │ F21 │ F22 │  ← Top
├─────┼─────┤  ├─────┼─────┤  ├─────┼─────┤
│ F15 │ F16 │  │ F19 │ F20 │  │ F23 │ F24 │  ← Bottom
└─────┴─────┘  └─────┴─────┘  └─────┴─────┘
```

## Files to Modify

When changing the mouse layer, **both files must be updated together**:

| File                         | Purpose            | What to change                             |
| ---------------------------- | ------------------ | ------------------------------------------ |
| `config/mouse.dtsi`          | ZMK signal defines | Modifier combos, F-key assignments         |
| `zmk-pointer/zmk_pointer.py` | Daemon logic       | Key mappings, activation modifiers, speeds |
| `keymap-drawer/config.yaml`  | Visualization      | `raw_binding_map` entries for new signals  |

## How to add a combo

1. Add key-position define(s) in the `combos` block of [config/hillside46.keymap](config/hillside46.keymap).
  - Naming rule: use `COMBO_KEYS_*` as a **prefix** (not suffix).
  - Add an inline comment with the triggering letters.
  - Example: `#define COMBO_KEYS_SYM_PLUS 6 7 // "yu"`
2. Add the combo binding in [config/combos.dtsi](config/combos.dtsi) with a guarded `#ifdef`.
  - Example:
    - `#ifdef COMBO_KEYS_SYM_PLUS`
    - `COMBO(sym_plus, &kp PLUS, COMBO_KEYS_SYM_PLUS, BASE_L, DEFAULT_TIMEOUT)`
    - `#endif`
  - Naming rule: behavior name should describe the output only (e.g. `sym_plus`), not the chord letters.
3. Optional: add combo rendering tweaks in [keymap-drawer/config.yaml](keymap-drawer/config.yaml) under `zmk_combos`.

Notes:
- Keep one meaning per chord (same key pair should not map to two different outputs).
- Use `BASE_L` unless you intentionally want a layer-specific combo.
- Prefer `DEFAULT_TIMEOUT` for normal combos and `DEFAULT_LEFT_TIMEOUT` for very tight same-hand combos.

### Example: Adding a new movement mode

1. **mouse.dtsi** - Add defines:
   ```c
   #define SIG_NEW_UP    LS(LC(F_KEY))
   ```

2. **zmk_pointer.py** - Add key mapping:
   ```python
   MOVEMENT_KEYS_NEW: dict[str, tuple[int, int]] = {
       "fXX": (0, -1),  # direction
   }
   ```

3. **config.yaml** - Add visualization:
   ```yaml
   '&kp SIG_NEW_UP': ↑ new
   ```

---

# TODO

- [ ] Num layer
  - [ ] Implement numword
  - [ ] Write a small paragraph
- [ ] Documentation
  - [ ] Add that it should work with the intl dead key layout
- [ ] Deep sleep modes
- [ ] Rework symbol layer
  - [ ] Change brackets to be near by
  - [ ] Use one left and one right sym layer
- [ ] Misc
  - [ ] Should implement the to start and to end as combo on nav layer as it is really usefull