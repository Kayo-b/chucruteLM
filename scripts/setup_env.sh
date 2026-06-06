#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
venv_dir="${repo_root}/.venv"
python_bin="${venv_dir}/bin/python"

cd "${repo_root}"

if [[ ! -x "${python_bin}" ]]; then
  echo "Creating virtual environment at ${venv_dir}"
  python -m venv "${venv_dir}"
fi

echo "Installing project in editable mode"
"${python_bin}" -m pip install -e .

echo
cat <<'EOF'
Setup complete.

Use one of these options to run project commands:

1) Activate the venv in your shell
   source .venv/bin/activate

2) Use the venv Python directly
   ./.venv/bin/python scripts/record_session.py --help
EOF
