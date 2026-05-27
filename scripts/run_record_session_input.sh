#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

cd "${repo_root}"

if ! getent group input >/dev/null; then
  echo "The 'input' group does not exist on this system." >&2
  exit 1
fi

if id -nG | tr ' ' '\n' | grep -Fxq input; then
  exec "${script_dir}/run_record_session.sh" "$@"
fi

exec sg input -c "$(printf '%q ' "${script_dir}/run_record_session.sh" "$@")"
