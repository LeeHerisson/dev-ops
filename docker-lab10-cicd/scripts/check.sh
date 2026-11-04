#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE="${IMAGE:-devops-lab10-todo:local}"
NAME="devops-lab10-check-$$"
mkdir -p evidence
docker build --target test -t devops-lab10-todo:test .
docker build --target runtime -t "$IMAGE" .
docker run --rm "$IMAGE" python -c \
  "import importlib.util,os; assert importlib.util.find_spec('pytest') is None; assert os.getuid() != 0; print('non-root runtime without pytest: OK')"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run -d --name "$NAME" -p 127.0.0.1::5000 "$IMAGE" >/dev/null
PORT=$(docker inspect "$NAME" --format '{{(index (index .NetworkSettings.Ports "5000/tcp") 0).HostPort}}')
python3 scripts/http_check.py "http://127.0.0.1:$PORT" | tee evidence/http-check.json
docker image inspect "$IMAGE" --format '{{.Id}} {{.Size}} {{.Os}}/{{.Architecture}}' | tee evidence/image.txt
docker stop -t 5 "$NAME" >/dev/null
EXIT_CODE=$(docker inspect "$NAME" --format '{{.State.ExitCode}}')
test "$EXIT_CODE" -eq 0
printf 'Graceful shutdown exit code: %s\n' "$EXIT_CODE" | tee evidence/shutdown.txt
