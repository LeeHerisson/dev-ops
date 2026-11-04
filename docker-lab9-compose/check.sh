#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"
cd "$LAB_ROOT"
assert_owned_resources
"${PYTHON:-python3}" tests/check.py
