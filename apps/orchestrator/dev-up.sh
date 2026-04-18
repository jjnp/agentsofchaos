#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

cd "$REPO_ROOT"
docker build -f apps/pi-worker/Dockerfile -t agentsofchaos/pi-worker:latest .

cd "$REPO_ROOT/apps/orchestrator"
docker compose up --build
