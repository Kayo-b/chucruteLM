#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

cd "${repo_root}"

# On Wayland, evdev reads /dev/input/event* and requires the 'input' group.
# On X11, pynput hooks into the display server and needs no special permissions.
_is_wayland() {
  [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]] \
    || [[ -n "${WAYLAND_DISPLAY:-}" ]] \
    || [[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]
}

if _is_wayland; then
  if ! getent group input >/dev/null; then
    echo "The 'input' group does not exist on this system." >&2
    exit 1
  fi

  if id -nG | tr ' ' '\n' | grep -Fxq input; then
    exec "${script_dir}/run_record_session.sh" "$@"
  fi

  exec sg input -c "$(printf '%q ' "${script_dir}/run_record_session.sh" "$@")"
fi

exec "${script_dir}/run_record_session.sh" "$@"
