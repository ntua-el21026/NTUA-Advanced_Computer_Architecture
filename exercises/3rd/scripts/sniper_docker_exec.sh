#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/../../.." && pwd)
IMAGE=${ADVCA_SNIPER_IMAGE:-advca-sniper:8.0}

exec docker run --rm \
    --user "$(id -u):0" \
    --mount "type=bind,src=$REPO_ROOT,dst=$REPO_ROOT" \
    --workdir "$REPO_ROOT" \
    --entrypoint /root/sniper/run-sniper \
    "$IMAGE" \
    "$@"
