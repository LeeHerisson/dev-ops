#!/usr/bin/env bash
set -euo pipefail
LAB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

dc() {
  docker compose --project-directory "$LAB_ROOT" -f "$LAB_ROOT/compose.yaml" "$@"
}

assert_owned_resources() {
  local container resource owner
  for container in devops-lab9-api devops-lab9-db devops-lab9-redis; do
    if docker container inspect "$container" >/dev/null 2>&1; then
      owner="$(docker container inspect --format '{{index .Config.Labels "devops.lab"}}' "$container")"
      [[ "$owner" == 9 ]] || { printf 'Refusing another project container: %s\n' "$container" >&2; return 1; }
    fi
  done
  for resource in devops-lab9-postgres-data devops-lab9-redis-data; do
    if docker volume inspect "$resource" >/dev/null 2>&1; then
      owner="$(docker volume inspect --format '{{index .Labels "devops.lab"}}' "$resource")"
      [[ "$owner" == 9 ]] || { printf 'Refusing another project volume: %s\n' "$resource" >&2; return 1; }
    fi
  done
  if docker network inspect devops-lab9-backend >/dev/null 2>&1; then
    owner="$(docker network inspect --format '{{index .Labels "devops.lab"}}' devops-lab9-backend)"
    [[ "$owner" == 9 ]] || { printf 'Refusing another project network\n' >&2; return 1; }
  fi
}
