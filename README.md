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

## Setup

On most modern Linux distributions (especially Arch, Ubuntu 23.10+, Fedora, etc.), Python enforces [PEP 668](https://peps.python.org/pep-0668/) which prevents package installation outside of a virtual environment.

**Create a virtual environment:**

```bash
python -m venv .venv
source .venv/bin/activate
```

**Then install the project:**

```bash
pip install -e .
```

After setup, always activate the venv before running scripts:

```bash
source .venv/bin/activate
```

Or use the venv Python directly without activating:

```bash
./.venv/bin/python scripts/record_session.py ...
```

## Quick start

Once the venv is set up and activated:

```bash
./scripts/setup_env.sh

# Optional for current shell session
source .venv/bin/activate

# Record a Tibia screen region on X11 or Hyprland
python scripts/record_session.py \
  --output data/session-001 \
  --fps 5 \
  --duration 10 \
  --profile-name tibia \
  --input-device /dev/input/eventX \
  --input-device /dev/input/eventY

# Inspect the recording
python scripts/inspect_dataset.py --data data/session-001

# Or use the wrapper for a timed session with an auto-generated output directory.
# It resolves the current Corne Keyboard and Logitech G502 HERO event devices on each run.
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

# Or use the shell wrapper to always run with the uinput backend
./scripts/run_live_policy.sh \
  --checkpoint output/base-policy \
  --fps 5 \
  --profile-name tibia \
  --print-actions

# If your current shell is missing refreshed group membership, use the group wrapper
./scripts/run_live_policy_input.sh \
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

`scripts/run_record_session.sh` now auto-resolves the readable evdev paths for:

- `ZMK Project Corne Keyboard` as the keyboard device
- `Logitech G502 HERO Gaming Mouse` as the mouse device

Live action emission uses a separate backend:

- `noop`: prediction-only dry run, prints actions but sends nothing
- `uinput`: emits Linux keyboard/mouse button events through a virtual input device, including
  relative pointer motion for Tibia tile-click actions

`uinput` requires `/dev/uinput` to exist and be writable.

If live policy fails with `evdev.uinput.UInputError: "/dev/uinput" cannot be opened for writing`,
fix permissions for `/dev/uinput`.

Quick temporary workaround:

```bash
sudo modprobe uinput
sudo chmod 666 /dev/uinput
```

Recommended persistent setup:

```bash
sudo groupadd -f uinput
sudo usermod -aG uinput "$USER"
sudo tee /etc/udev/rules.d/99-uinput.rules >/dev/null <<'EOF'
KERNEL=="uinput", MODE="0660", GROUP="uinput", OPTIONS+="static_node=uinput"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Then log out and back in (or reboot) so new group membership is applied.

Tibia live execution pulses keyboard actions by default instead of holding them indefinitely, which
fits tile-based movement and shortcut-style hotkeys better than a raw key-down latch.

The Tibia profile also includes discrete tile-click actions around the player
(`click_tile_north`, `click_tile_south`, `click_tile_east`, `click_tile_west`, plus diagonals).
Use `--tibia-viewport-left`, `--tibia-viewport-top`, `--tibia-viewport-width`,
`--tibia-viewport-height`, `--tibia-grid-width`, `--tibia-grid-height`,
`--tibia-center-x`, and `--tibia-center-y` to calibrate the playable map viewport inside the
captured Tibia window. The live runner tracks pointer clicks relative to an initial cursor
position; by default it uses the configured viewport center, and you can override that with
`--pointer-start-x` / `--pointer-start-y`.

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
