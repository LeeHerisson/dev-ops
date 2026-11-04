#!/usr/bin/env bash
set -euo pipefail
LAB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAB_NETWORK=devops-lab6-network
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
BACKEND_PORT="${BACKEND_PORT:-5000}"
CONTAINERS=(devops-lab6-frontend devops-lab6-backend devops-lab6-redis)

require_owned_container() {
  local owner
  owner="$(docker inspect --format '{{index .Config.Labels "devops.lab"}}' "$1")"
  if [[ "$owner" != 6 ]]; then
    printf 'Refusing to change container with another owner: %s\n' "$1" >&2
    return 1
  fi
}

wait_healthy() {
  local container="$1" state
  for ((attempt=1; attempt<=40; attempt++)); do
    state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")"
    if [[ "$state" == healthy ]]; then return 0; fi
    if [[ "$state" == exited || "$state" == dead ]]; then break; fi
    sleep 2
  done
  docker logs --tail 40 "$container" >&2
  printf 'Container is not healthy: %s\n' "$container" >&2
  return 1
}
