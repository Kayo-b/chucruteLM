# chucruteLM

`chucruteLM` is now a **Tibia-first** screen-only behavioral-cloning project.

The current `main` branch focuses on the concrete Tibia pipeline:

- capture pixels from a desktop window or region
- convert the frame into an ASCII grid representation
- attach extracted numeric UI values
- align the observation with keyboard and mouse input
- train a compact behavioral-cloning policy
- run the trained policy live through a Linux action backend

The default policy configuration lands at roughly **1.7M parameters**, which keeps the current stack in the intended tiny-model range while leaving room for later Tibia-specific extractors and control logic.

The strategy is to finish Tibia end-to-end first, then extract smaller reusable abstractions later instead of designing a broad multi-game framework up front.

## Current branch strategy

- `main`: Tibia-focused implementation
- future branches: extract or adapt patterns for other games only after the Tibia pipeline is proven

## Quick start

```bash
pip install -e .

# Record a Tibia screen region on X11 or Hyprland
python scripts/record_session.py \
  --output data/session-001 \
  --fps 5 \
  --duration 10 \
  --profile-name tibia \
  --input-device /dev/input/event17

# Inspect the recording
python scripts/inspect_dataset.py --data data/session-001

# Or use the wrapper for a timed session with an auto-generated output directory
./scripts/run_record_session.sh 10

# If your current shell is missing the `input` group, use the group wrapper
./scripts/run_record_session_input.sh 10

# Train a compact policy model
python scripts/train_behavior_cloner.py \
  --data data/session-001 \
  --output output/base-policy \
  --profile-name tibia

# Run the trained policy live (dry-run by default; use --action-backend uinput to emit input)
python scripts/run_live_policy.py \
  --checkpoint output/base-policy \
  --fps 5 \
  --profile-name tibia \
  --print-actions
```

The Tibia profile currently defaults to:

- movement: arrows and `WASD`
- diagonals: keypad `7/9/1/3` plus their common navigation-key equivalents
- combat: `left` click for attack/interact, `right` click for context use, `space` for next target
- hotkeys: `F1` through `F12`
- client shortcuts such as `Ctrl+B`, `Ctrl+S`, `Alt+S`, `Ctrl+U`, `Ctrl+Q`, and chat tab cycling
- window detection: auto-matches the open Hyprland Tibia client (`com.tibia.client` / `Tibia`) if no manual region is passed

On X11 the recorder auto-selects `mss` + `pynput`. On Hyprland/Wayland it auto-selects
`grim` + `evdev`. Hyprland capture therefore requires `grim` on `PATH`, and input capture
requires permission to read `/dev/input/event*`. You can override either choice with
`--capture-backend` / `--input-backend`, and you can pin specific evdev devices with repeated
`--input-device /dev/input/event...` flags.

Live action emission uses a separate backend:

- `noop`: prediction-only dry run, prints actions but sends nothing
- `uinput`: emits Linux keyboard/mouse button events through a virtual input device

`uinput` requires `/dev/uinput` to exist and be writable.

Tibia live execution pulses keyboard actions by default instead of holding them indefinitely, which
fits tile-based movement and shortcut-style hotkeys better than a raw key-down latch.

To inspect the available evdev paths before recording:

```bash
python scripts/record_session.py --list-input-devices
```

When `evdev` is available, this prints each device path together with its detected name and
whether it looks like a keyboard, mouse, or pointer device.

To inspect detectable windows:

```bash
python scripts/record_session.py --list-windows
```

Custom bindings use `|` for alternatives and `+` for simultaneous combos, for example
`--key-binding move_up=up|w` or `--key-binding open_battle_list=ctrl_l+b`.

## Main-branch package layout

```text
src/chucrutelm/
  ascii/       # Frame-to-ASCII conversion
  capture/     # Linux-first screen capture and input observation
  control/     # Linux action emission and runtime actuation
  data/        # Recording pipeline and dataset serialization
  inference/   # Runtime prediction helpers
  model/       # Tiny policy model and tokenizer
  profiles/    # Tibia-first action bindings and future state extractors
  training/    # Behavioral cloning dataset + trainer
scripts/       # CLI entrypoints
tests/         # Base unit tests
```
