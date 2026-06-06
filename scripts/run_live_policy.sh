#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <checkpoint-dir> [run_live_policy.py args...]" >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

cd "${repo_root}"

python_bin="python"
if [[ -x "${repo_root}/.venv/bin/python" ]]; then
  python_bin="${repo_root}/.venv/bin/python"
fi

if [[ ! -e /dev/uinput ]]; then
  echo "Missing /dev/uinput. Load the kernel module first:" >&2
  echo "  sudo modprobe uinput" >&2
  exit 1
fi

if [[ ! -w /dev/uinput ]]; then
  echo "/dev/uinput is not writable by user '${USER}'." >&2
  echo "Current permissions:" >&2
  ls -l /dev/uinput >&2 || true
  echo >&2
  echo "Temporary fix (for this boot/session):" >&2
  echo "  sudo chmod 666 /dev/uinput" >&2
  echo >&2
  echo "Persistent fix (recommended):" >&2
  echo "  1) sudo groupadd -f uinput" >&2
  echo "  2) sudo usermod -aG uinput ${USER}" >&2
  echo "  3) Create /etc/udev/rules.d/99-uinput.rules with:" >&2
  echo "       KERNEL==\"uinput\", MODE=\"0660\", GROUP=\"uinput\", OPTIONS+=\"static_node=uinput\"" >&2
  echo "  4) sudo udevadm control --reload-rules && sudo udevadm trigger" >&2
  echo "  5) Re-login (or reboot)" >&2
  exit 1
fi

exec "${python_bin}" scripts/run_live_policy.py --action-backend uinput "$@"
