#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"
cd "$LAB_ROOT"
docker info >/dev/null

# Validate every existing named resource before changing any of them.
for container in "${CONTAINERS[@]}"; do
  if docker inspect "$container" >/dev/null 2>&1; then
    require_owned_container "$container"
  fi
done
if docker network inspect "$LAB_NETWORK" >/dev/null 2>&1; then
  owner="$(docker network inspect --format '{{index .Labels "devops.lab"}}' "$LAB_NETWORK")"
  [[ "$owner" == 6 ]] || { printf 'Network belongs to another project\n' >&2; exit 1; }
fi

docker build --label devops.lab=6 -t devops-lab6-backend:1.0 ./backend
docker build --label devops.lab=6 -t devops-lab6-frontend:1.0 ./frontend
bash ./stop.sh --containers-only
if ! docker network inspect "$LAB_NETWORK" >/dev/null 2>&1; then
  docker network create --driver bridge --label devops.lab=6 "$LAB_NETWORK"
fi

docker run -d --name devops-lab6-redis --label devops.lab=6 \
  --network "$LAB_NETWORK" --network-alias redis \
  --mount type=tmpfs,destination=/data \
  --health-cmd 'redis-cli ping | grep -q PONG' \
  --health-interval 3s --health-timeout 2s --health-retries 15 \
  redis:7-alpine redis-server --save '' --appendonly no
wait_healthy devops-lab6-redis

docker run -d --name devops-lab6-backend --label devops.lab=6 \
  --network "$LAB_NETWORK" --network-alias backend \
  -e REDIS_HOST=redis -e REDIS_PORT=6379 \
  -p "127.0.0.1:${BACKEND_PORT}:5000" devops-lab6-backend:1.0
wait_healthy devops-lab6-backend

docker run -d --name devops-lab6-frontend --label devops.lab=6 \
  --network "$LAB_NETWORK" --network-alias frontend \
  -p "127.0.0.1:${FRONTEND_PORT}:80" devops-lab6-frontend:1.0
wait_healthy devops-lab6-frontend
printf 'Frontend: http://localhost:%s\nBackend: http://localhost:%s\n' "$FRONTEND_PORT" "$BACKEND_PORT"
