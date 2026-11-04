#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"
cd "$LAB_ROOT"
export FRONTEND_PORT BACKEND_PORT
"${PYTHON:-python3}" tests/check.py
