#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"
cd "$LAB_ROOT"
docker info >/dev/null
assert_owned_resources
bash ./configure.sh
dc config --quiet
dc up --build -d --wait --wait-timeout 120
dc ps
printf 'Lab 9 is ready. Default API: http://localhost:5059\n'
