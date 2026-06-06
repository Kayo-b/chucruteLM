# chucruteLM — Implementation Status

> Analysis relative to the SauerkrautLM-Doom-MultiVec-1.3M reference implementation.
> Generated: 2026-06-06

---

## Reference: SauerkrautLM-Doom-MultiVec-1.3M

A 1.3M-parameter ModernBERT agent that plays DOOM's `defend_the_center` scenario via behavioral
cloning. Key design choices:

- **Semantic ASCII**: VizDoom's labels buffer overlays `E`/`W`/`H`/`A` characters on the brightness
  ramp — the model is explicitly told what is an enemy, wall, health pickup, etc.
- **Depth buffer**: per-token depth bin IDs added to char embeddings before the transformer,
  giving the model a sense of 3D distance.
- **Perfect synchronous labels**: `game.get_state()` → human plays → `game.get_last_action()`
  returns a clean button vector with zero ambiguity.
- **No mouse**: DOOM turns are two discrete buttons (`turn_left` / `turn_right`). The aiming
  problem does not exist in that setup.
- **Soft labels + KL-divergence**: action affinities (turning slightly implies some forward
  motion) smooth the training signal.
- **Transformer backbone**: 5-layer ModernBERT with attention pooling; can attend across the
  full ~1024-char frame.

---

## Current chucruteLM Status

### ✅ What is in place and theoretically working

| Component | File(s) | Notes |
|-----------|---------|-------|
| Screen capture | `capture/linux.py` | Auto-selects `mss` (X11) or `grim` (Wayland/Hyprland) |
| Keyboard input logging | `capture/linux.py` | Pressed + tapped keys via `pynput` or `evdev` |
| Mouse button logging | `capture/linux.py` | Pressed + tapped buttons (left/right/middle) |
| Synchronized recording | `data/recording.py` | Fixed-FPS loop: capture + input snapshot per frame |
| JSONL dataset format | `data/recording.py` | One JSON record per frame → `manifest.jsonl` |
| ASCII grid encoding | `ascii/converter.py` | Grayscale resize → brightness ramp → char grid |
| Action inference (keys/buttons) | `profiles/base.py` | Binding lookup: key/button combo → action name |
| Tibia action space definition | `profiles/tibia.py` | 43 named actions including tile-click actions |
| Tibia key + button bindings | `profiles/tibia.py` | Arrow/WASD, diagonals, F1–F12, combos, left/right click |
| Behavioral cloning dataset | `training/dataset.py` | Loads JSONL, filters labeled frames, encodes grid |
| Policy model | `model/policy.py` | Embedding → Residual ConvNet → AdaptiveAvgPool → Classifier (~1.7M params) |
| Training pipeline | `training/trainer.py` | Cross-entropy, AdamW, train/eval split, checkpoint save |
| Policy runtime | `inference/runtime.py` | Loads checkpoint, ASCII → action name |
| Live inference loop | `inference/live.py` | Capture → ASCII → model → execute at fixed FPS |
| Tile-click **execution** | `control/linux.py` + `profiles/tibia.py` | `tile_to_screen()` → relative `uinput` mouse move + click |
| Uinput virtual device | `control/linux.py` | Keys, buttons, and `REL_X`/`REL_Y` via `/dev/uinput` |
| Noop dry-run backend | `control/linux.py` | Prediction-only, prints actions, sends nothing |
| Window auto-detection | `capture/linux.py` | Matches Tibia window by class / title on Hyprland |

---

### ❌ Critical gaps (block end-to-end correctness)

#### 1. Mouse coordinates are never recorded

`ActionEvent` stores `pressed_buttons` and `tapped_buttons` but **no (x, y) position**.
The evdev observer accumulates `REL_X`/`REL_Y` deltas for movement but does not expose
the cursor's absolute position at the moment of a click.

**Consequence**: it is impossible to label tile-click actions from recorded human play.

#### 2. Tile-click actions can never appear in training data

`TIBIA_BUTTON_BINDINGS` maps:

```python
"attack_interact": (("left",),)   # any left click → attack_interact
"context_use":     (("right",),)  # any right click → context_use
```

There are **no bindings** for `click_tile_north`, `click_tile_south`, etc.
`infer_action()` will **never** return a tile-click label.
All 8 tile-click actions exist in the action space and execution layer but are **dead weight
in training** — they will never appear in any training batch.

**Fix needed**:
1. Track cursor absolute position in the input observer (accumulate `REL_X`/`REL_Y` from a
   known starting point, or read `/sys/class/input` absolute state).
2. Record `click_x`, `click_y` alongside button presses in `ActionEvent` / `Observation`.
3. Add an inverse of `tile_to_screen()` — given `(click_x, click_y)` and the viewport config,
   find the nearest tile offset `(dx, dy)` → map to `click_tile_*` action name.
4. Use this in `infer_action()` during recording (and in dataset loading).

#### 3. ASCII encoding is brightness-only — no semantic content

The current converter:
```
Tibia RGB frame → grayscale → resize 80×60 → brightness → charset char
```

The characters carry **no semantic meaning**. A wall and a walkable floor tile produce the
same character if they share the same average grayscale brightness. The model has no concept
of "wall", "floor", "creature", or "item" — only brightness gradients.

**Contrast with Doom**: VizDoom's labels buffer overlays `W`/`E`/`H`/`A`/`D` using the
game engine's semantic segmentation. chucruteLM has no equivalent because Tibia is an
opaque client.

**Consequence**: the model must learn spatial patterns from brightness alone. This is
possible for areas where brightness correlates with passability (e.g. consistently darker
walls), but is unreliable across different Tibia zones and map areas.

**Fix options** (in order of impact vs effort):
- **Keep RGB / multi-channel** — color distinguishes walls from floors far better than
  luminance. Tibia walls and floor tiles differ strongly in hue.
- **Minimap parsing** — Tibia's minimap uses explicit color coding (dark brown = wall,
  light = floor). A color threshold on that UI region gives a reliable walkability grid.
- **Semantic charset overlay** — classify each tile block before the brightness mapping and
  assign meaningful characters (`W`=wall, `.`=floor, `E`=creature, `I`=item).
- **Tile sprite template matching** — Tibia reuses a fixed sprite set; matching known sprites
  gives perfect tile-type labels.

---

### ⚠️ Secondary gaps (degrade quality, not blockers)

| Gap | Impact | Notes |
|-----|--------|-------|
| `NullUiExtractor` — no HP/mana/level extraction | `numeric_features` is always `{}` | Model has zero game-state awareness (health, mana, level, skills) |
| Hard labels only (cross-entropy) | Less robust training signal | Doom used soft KL-divergence with action affinities; overlapping actions (e.g. moving while clicking) are ambiguous with hard labels |
| Single-frame model, no temporal context | Cannot learn sequences, cooldowns, or reactions | A single ASCII snapshot contains no information about what just happened |
| Pointer drift at execution | Accuracy degrades over time | `_pointer_position` is tracked in software memory. Real OS cursor can desync (window resize, other input) with no recovery mechanism |
| No cursor warp / absolute reset at execution start | Compound drift on long runs | No mechanism to anchor the cursor to the viewport center before a session starts |
| CNN backbone vs transformer | Lower quality spatial reasoning | The CNN can learn local patterns; a transformer (like Doom's ModernBERT) can attend across the full frame and relate distant landmarks |

---

## Architecture Comparison

| Aspect | SauerkrautLM-Doom | chucruteLM (current) |
|--------|-----------------|----------------------|
| Backbone | 5-layer ModernBERT (transformer, attention pooling) | Residual CNN → AdaptiveAvgPool → MLP |
| Input encoding | Char token IDs + per-token depth bin IDs (additive) | Char token IDs only |
| ASCII semantics | Semantic overlay (`E`/`W`/`H`/`A`/`D`) via game labels buffer | Pure brightness ramp — no semantic meaning |
| Extra sensor | VizDoom depth buffer (16 quantized bins per pixel) | None (`NullUiExtractor`) |
| Action space | 4 (all discrete keys, no mouse) | 43 (keys + buttons + 8 tile-clicks) |
| Mouse | None — aiming is `turn_left`/`turn_right` | Relative uinput moves at inference; not learnable from recordings |
| Labels | Soft scores + KL-divergence with affinities | Hard labels, cross-entropy |
| Recording sync | VizDoom API (perfect, zero-latency) | Wall-clock FPS sampling (evdev/pynput) |
| Temporal context | Single frame | Single frame |
| Parameters | ~1.3M | ~1.7M |

---

## Priority Fix List

1. **[BLOCKER] Record mouse position + label tile-click actions**
   Without this, the 8 tile-click actions are permanently absent from training.
   The fix lives in `capture/linux.py` (expose cursor position) + `profiles/tibia.py`
   (inverse tile mapping) + `schemas.py` (add coordinate fields).

2. **[HIGH] Replace grayscale brightness encoding with color-aware or semantic encoding**
   At minimum: keep RGB as 3 separate channels. Ideally: add a semantic charset overlay
   for the most common tile categories (wall, floor, creature, item).

3. **[MEDIUM] Implement `TibiaUiExtractor`**
   Extract HP, mana, level from known pixel regions of the Tibia UI.
   These are the `numeric_features` that are currently always empty.

4. **[MEDIUM] Add cursor position reset / anchor at execution start**
   Warp or confirm cursor position to viewport center before live policy begins.

5. **[LOW] Soft labels for overlapping actions**
   Replace hard cross-entropy labels with soft scores for frames where multiple
   actions are plausible (e.g. moving while hotkey is pressed).

6. **[LOW] Temporal context**
   Stack N consecutive frames or add a recurrent/attention layer so the model
   can react to sequences of events rather than each frame in isolation.
