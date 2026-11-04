#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"
assert_owned_resources
dc down
printf 'Only lab 9 containers/network removed. Named data volumes retained.\n'
