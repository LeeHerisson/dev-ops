#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"
for container in "${CONTAINERS[@]}"; do
  if docker inspect "$container" >/dev/null 2>&1; then
    require_owned_container "$container"
  fi
done
for container in "${CONTAINERS[@]}"; do
  if docker inspect "$container" >/dev/null 2>&1; then
    docker stop --time 10 "$container" >/dev/null
    docker rm "$container" >/dev/null
  fi
done
if [[ "${1:-}" != --containers-only ]] && docker network inspect "$LAB_NETWORK" >/dev/null 2>&1; then
  owner="$(docker network inspect --format '{{index .Labels "devops.lab"}}' "$LAB_NETWORK")"
  [[ "$owner" == 6 ]] || { printf 'Network belongs to another project\n' >&2; exit 1; }
  docker network rm "$LAB_NETWORK" >/dev/null
fi
printf 'Lab 6 containers stopped and removed. Other projects unchanged.\n'
