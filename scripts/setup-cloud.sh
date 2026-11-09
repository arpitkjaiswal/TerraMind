#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root/frontend"
npm ci --cache /workspace/.npm-cache
cd "$project_root/backend"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd "$project_root"
python3 -m venv /workspace/.venvs/terramind-ml
/workspace/.venvs/terramind-ml/bin/python -m pip install -r requirements_ml.txt
