#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <duration-seconds> [output-dir]" >&2
  exit 1
fi

duration="$1"
output_dir="${2:-data/session-$(date +%Y%m%d-%H%M%S)}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

cd "${repo_root}"

python_bin="python"
if [[ -x "${repo_root}/.venv/bin/python" ]]; then
  python_bin="${repo_root}/.venv/bin/python"
fi

mapfile -t input_devices < <("${python_bin}" scripts/resolve_record_input_devices.py)

cmd=(
  "${python_bin}" scripts/record_session.py
  --output "${output_dir}"
  --fps 5
  --duration "${duration}"
  --profile-name tibia
)

for device in "${input_devices[@]}"; do
  echo "${device}"
  cmd+=(--input-device "${device}")
done

exec "${cmd[@]}"
