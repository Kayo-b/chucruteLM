# Current technical setup

## Scope

This document describes the current state of the `chucruteLM` Tibia-first recording/training/runtime workflow on this repository, including the current Hyprland-specific setup and the main gaps still remaining.

The current strategy is to complete the Tibia pipeline first and only extract reusable abstractions later if they emerge naturally from working game-specific code.

## Current pipeline

### 1. Session recording

The main recorder entrypoint is:

```bash
python scripts/record_session.py
```

At each sampling tick, the recorder:

1. captures a screen region
2. converts the captured frame to grayscale and then to ASCII
3. snapshots current keyboard/mouse state
4. infers an action label from configured bindings
5. appends a JSONL record to disk

The synchronized loop lives in `src/chucrutelm/data/recording.py`.

Each manifest row contains:

- `observation.ascii_text`: ASCII representation of the sampled frame
- `observation.raw_inputs`: normalized pressed keys/buttons, pointer, scroll
- `action.action_name`: bound action name if an input binding matched
- `action.pressed_keys` / `action.pressed_buttons`: the normalized inputs used for labeling

The recorder writes:

- `manifest.jsonl`
- `metadata.json`
- `frames/` only if `--save-frames` is enabled

For the Tibia profile, if no explicit `--left/--top/--width/--height` region is passed, the
recorder now auto-resolves the currently open Tibia client window from Hyprland window metadata.

### 2. Capture backend selection

Capture is selected automatically in `src/chucrutelm/capture/linux.py`.

- **X11**: `mss`
- **Hyprland / Wayland**: `grim`

The current Hyprland runs therefore use:

- `capture_backend = grim`
- `input_backend = evdev`

### 3. Input capture

Input backend selection is also handled in `src/chucrutelm/capture/linux.py`.

- **X11**: `pynput`
- **Hyprland / Wayland**: `evdev`

The wrapper now resolves the target devices by name on each run:

```text
Corne Keyboard
Logitech G502 HERO
```

This resolution is wired into the wrapper script:

```bash
scripts/run_record_session.sh
```

using the Tibia default profile bindings.

### 4. Wrapper scripts

Two shell helpers exist:

#### `scripts/run_record_session.sh`

Purpose:

- run a timed recording session
- accept duration as the first parameter
- accept an optional output directory as the second parameter

Current defaults:

- region: auto-detected from the open Tibia client window when available
- fps: `5`
- input devices: auto-resolved on each run for `Corne Keyboard` and `Logitech G502 HERO`
- profile: `tibia`

Example:

```bash
./scripts/run_record_session.sh 10 data/session-003
```

#### `scripts/run_record_session_input.sh`

Purpose:

- re-run the previous wrapper through the `input` group if the current shell is missing that group

Example:

```bash
./scripts/run_record_session_input.sh 10 data/session-003
```

## Current dataset behavior

### What is working

- Hyprland screen capture works through `grim`
- evdev-based input capture works structurally
- manifest and metadata are produced correctly
- training can consume labeled manifest rows
- inference checkpoint loading exists through `src/chucrutelm/inference/runtime.py`

### Current observed behavior

Recent recordings showed that:

- metadata files were correct
- screen frames were recorded
- input snapshots were recorded
- labels stayed `unlabeled` when bindings did not match the actual normalized keys

This means the recorder itself is functioning, but **training-quality labels depend entirely on the selected device and the exact normalized key names emitted by that device**.

### Important operational detail

Recording into an existing output directory appends to the existing `manifest.jsonl`.

That means:

- reusing `data/session-001` or `data/session-002` mixes runs
- `inspect_dataset.py` will report totals across all appended runs

Use a fresh output directory for each new session.

## Training and inference

### Training

Training entrypoint:

```bash
python scripts/train_behavior_cloner.py --data ... --output ... --profile-name tibia
```

Training output:

- `model.pt`
- `metadata.json`

### Inference

The repository already has an offline runtime loader:

```python
from chucrutelm.inference import PolicyRuntime
```

`PolicyRuntime` can:

- load `model.pt`
- load training metadata
- encode a new ASCII observation
- return the predicted action and logits

### Live runtime

The repository now also has a generic live runtime path:

```bash
python scripts/run_live_policy.py \
  --checkpoint output/base-policy \
  --profile-name tibia \
  --print-actions
```

This path:

1. captures the selected screen region continuously
2. converts each frame to ASCII
3. runs `PolicyRuntime.predict(...)`
4. maps the predicted action to configured key/button bindings
5. emits Linux input events through either:
   - `noop` backend for dry runs
   - `uinput` backend for actual key/button output

The runtime loop lives in `src/chucrutelm/inference/live.py`.

The Linux action emission layer lives in `src/chucrutelm/control/linux.py`.

Current generic behavior:

- Tibia movement and shortcut actions are emitted as timed key pulses
- mouse attack/context actions are emitted as timed clicks
- alternative bindings are supported for recording (for example `up` or `w`)
- simultaneous shortcut combos are supported for both labeling and execution (for example `Ctrl+B`)
- the live runner supports repeat throttling for both key pulses and button clicks
- repeated actions are rate-limited by configurable repeat intervals
- all held keys are released on shutdown

## What is still missing

### 1. Better device selection UX

Input device listing exists, but the workflow is still manual.

Missing improvements:

- choose devices by name instead of raw `/dev/input/eventN`
- auto-detect the most likely keyboard/mouse
- better filtering for composite devices

### 2. Better binding/debug tooling

There is no dedicated debug command yet to show:

- raw normalized keys in real time
- which binding matched
- why a frame became `unlabeled`

That would make input setup much easier.

### 3. Mouse movement path

The current wrapper now targets both the Corne keyboard and the Logitech G502 HERO by resolving
their current `/dev/input/event*` paths before each recording run.

So:

- keyboard movement can be labeled if bindings match
- mouse clicks can be emitted by the live runtime if they are bound to an action
- pointer movement and coordinate-targeted clicks are still not modeled or emitted
- richer mouse workflows will need an explicit pointer-control abstraction

### 4. Game-specific feature extraction

The base branch currently records:

- ASCII frames
- empty numeric feature sets unless a game-specific profile adds UI extractors

So the current setup is still generic and does not yet include:

- health parsing
- mana parsing
- minimap parsing
- enemy counters
- other game-specific UI signals

### 5. Stronger documentation around permissions

Hyprland/Wayland requires access to `/dev/input/event*` for evdev.

Actual action emission also requires `/dev/uinput` to exist and be writable when using the
`uinput` backend.

The repository now documents this better, but a more complete setup section would still help:

- group membership refresh behavior
- ACL alternative
- per-device troubleshooting steps

## Bottom line

The repository now has a functional **screen -> ASCII -> input snapshot -> labeled dataset -> trainable checkpoint -> live predict/act loop** pipeline on `main`, provided that:

- the correct evdev device is used
- the shell has permission to read it
- the bindings match the normalized key names actually emitted
- the chosen output backend has permission to emit input

What it still does **not** have is game-specific orchestration such as pointer targeting,
hierarchical state routing, or custom UI feature extraction.

## todo

**Implement it in two layers:**  
1. make the runtime able to **emit mouse movement/clicks**, and  
2. change the policy/output format so it can choose **where** to click.

## 1. `uinput` access and real emitted input

For real Linux-emitted input, the runtime needs access to `/dev/uinput`.

### System side
You need:
```bash
ls -l /dev/uinput
```

If it exists but is restricted, grant access via group/udev. Typical setup:
```bash
sudo modprobe uinput
sudo usermod -aG input "$USER"
```

For persistent permissions, add a udev rule like:
```bash
KERNEL=="uinput", GROUP="input", MODE="0660"
```

Then reload udev / relogin.

### Code side
Right now `UinputActionBackend` only emits `EV_KEY`.  
To support pointer control, extend it to also register:

- `EV_REL`: `REL_X`, `REL_Y`
- optionally `REL_WHEEL`
- mouse buttons: `BTN_LEFT`, `BTN_RIGHT`

And add methods to the backend protocol:

```python
def move_pointer_rel(self, dx: int, dy: int) -> None: ...
def click_button(self, button_name: str) -> None: ...
```

Then in `UinputActionBackend`:

```python
capabilities = {
    ecodes.EV_KEY: key_codes + button_codes,
    ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y],
}
```

and emit:
```python
self._ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
self._ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
self._ui.syn()
```

## 2. Pointer-targeted Tibia clicks

The current model predicts discrete actions like `move_up` or `attack_interact`.  
That is **not enough** for Tibia click-to-move, because click-to-move needs coordinates.

You need a new action type, for example:

```python
@dataclass
class PointerAction:
    action_name: str
    pointer_target: tuple[int, int] | None = None
    button: str | None = None
```

Then the executor can do:

1. move pointer to `(x, y)`
2. press/release left mouse

## 3. Mapping Tibia world tiles to screen pixels

This is the key missing piece.

### Simplest practical approach
Treat the Tibia game viewport as a grid and click tile centers.

You need:
1. the Tibia window bounds — now auto-detected
2. the **playable map viewport** inside the window
3. visible grid dimensions, e.g. around the player
4. tile size in pixels

Then compute:

```python
screen_x = viewport_left + (tile_x + 0.5) * tile_width
screen_y = viewport_top + (tile_y + 0.5) * tile_height
```

If the player is centered, a relative move like `(dx=+1, dy=0)` maps to:
```python
tile_x = center_x + dx
tile_y = center_y + dy
```

### What to add in this repo
Add a Tibia-specific extractor/config, e.g.:
- `window padding / viewport rect`
- visible tile grid size
- player center tile

Something like:

```python
@dataclass
class TibiaViewport:
    left: int
    top: int
    width: int
    height: int
    grid_width: int
    grid_height: int
    center_x: int
    center_y: int
```

Then helper:

```python
def tile_to_screen(viewport: TibiaViewport, dx: int, dy: int) -> tuple[int, int]:
    tile_w = viewport.width / viewport.grid_width
    tile_h = viewport.height / viewport.grid_height
    x = viewport.left + (viewport.center_x + dx + 0.5) * tile_w
    y = viewport.top + (viewport.center_y + dy + 0.5) * tile_h
    return round(x), round(y)
```

## 4. Model/output changes

For click-to-move, discrete labels like `move_up` are a fallback, but not the ideal Tibia control space.

Better options:

### Option A: discrete click actions
Predict:
- `click_north`
- `click_south`
- `click_north_east`
- etc.

Easy to add, limited precision.

### Option B: relative tile target
Predict:
- button = left
- target tile offset `(dx, dy)`

Much better for Tibia.  
This likely means moving beyond the current pure classifier into:
- classifier for action type
- regressor or discrete grid head for target tile

## 5. Recommended implementation order

1. **Extend `UinputActionBackend`** with relative mouse movement.
2. **Add pointer methods** to `ActionOutputBackend` and `ActionExecutor`.
3. **Add a Tibia viewport config** and `tile_to_screen(...)`.
4. **Add new runtime actions** like `click_tile(dx, dy)`.
5. **Start with fixed discrete tile clicks** before changing the model architecture.
6. Later, upgrade training to learn tile targets directly.

## 6. Best near-term version

The fastest useful version on `main` is:

- keep current keyboard-pulse actions
- add `left_click_tile(dx, dy)` support in the executor
- hardcode/calibrate Tibia viewport bounds
- start with a small set of click targets near the player

That gets you real Tibia click-to-move **without** redesigning the whole ML stack first.

If you want, I can implement the **uinput mouse movement layer + Tibia tile-to-screen click executor** next.