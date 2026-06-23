#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/../../.." && pwd)
EXERCISE_DIR="$REPO_ROOT/exercises/3rd"
HELPCODE_DIR="$EXERCISE_DIR/advcomparch-ex3-helpcode"
IMAGE=${ADVCA_SNIPER_IMAGE:-advca-sniper:8.0}
BASE_IMAGE=snipersim/snipersim@sha256:4f10d4bbfee057e27a52fc0dc33087813feb504bbbfff22902984e356576eaed

usage() {
    echo "Usage: $0 <pull|build-image|check|build-binaries|smoke|run-4.1|run-4.2|shell>"
}

container() {
    docker run --rm \
        --user "$(id -u):0" \
        --mount "type=bind,src=$REPO_ROOT,dst=$REPO_ROOT" \
        --workdir "$REPO_ROOT" \
        "$@"
}

action=${1:-}
case "$action" in
    pull)
        docker pull "$BASE_IMAGE"
        ;;
    build-image)
        docker build \
            --file "$EXERCISE_DIR/docker/Dockerfile" \
            --tag "$IMAGE" \
            "$REPO_ROOT"
        ;;
    check)
        docker image inspect "$IMAGE" >/dev/null
        set +e
        container --entrypoint /bin/bash "$IMAGE" -lc \
            "test -x /root/sniper/run-sniper &&
             test -x /root/sniper/pin_kit/pin &&
             test -f /root/sniper/include/sim_api.h &&
             test -x /root/sniper/tools/advcomparch_mcpat.py &&
             echo 'Sniper container: PASS'"
        status=$?
        set -e
        if [[ $status -eq 139 ]]; then
            echo "Sniper container shell exited with status 139." >&2
            echo "Enable WSL kernelCommandLine=vsyscall=emulate as documented in scripts/README.md." >&2
            exit 139
        fi
        exit "$status"
        ;;
    build-binaries)
        container --entrypoint /usr/bin/make "$IMAGE" \
            -C "$HELPCODE_DIR" sniper SNIPER_BASE_DIR=/root/sniper
        ;;
    smoke)
        "$0" check
        "$0" build-binaries
        "$SCRIPT_DIR/run_4_1_sniper_scalability.py" \
            --no-build \
            --skip-mcpat \
            --run-sniper "$SCRIPT_DIR/sniper_docker_exec.sh" \
            --limit 1 \
            --force
        ;;
    run-4.1)
        "$0" check
        "$0" build-binaries
        "$SCRIPT_DIR/run_4_1_sniper_scalability.py" \
            --no-build \
            --run-sniper "$SCRIPT_DIR/sniper_docker_exec.sh" \
            --mcpat-script "$SCRIPT_DIR/mcpat_docker_exec.sh"
        ;;
    run-4.2)
        "$0" check
        "$0" build-binaries
        "$SCRIPT_DIR/run_4_2_topologies.py" \
            --no-build \
            --run-sniper "$SCRIPT_DIR/sniper_docker_exec.sh" \
            --mcpat-script "$SCRIPT_DIR/mcpat_docker_exec.sh"
        ;;
    shell)
        exec docker run --rm -it \
            --user "$(id -u):0" \
            --mount "type=bind,src=$REPO_ROOT,dst=$REPO_ROOT" \
            --workdir "$REPO_ROOT" \
            --entrypoint /bin/bash \
            "$IMAGE"
        ;;
    *)
        usage
        exit 2
        ;;
esac
