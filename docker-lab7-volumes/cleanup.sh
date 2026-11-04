#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ "$#" -lt 1 ]; then
  echo "Использование: ./cleanup.sh RUN_ID [--delete-data]" >&2
  exit 2
fi
run_id=$1
shift
exec python3 verify.py --cleanup --run-id "$run_id" "$@"
