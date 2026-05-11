#!/bin/bash
set -euo pipefail

CONTAINER_NAME="elevation_mapping_cupy_jazzy"
CONTAINER_WS="/home/ubuntu/workspace"
CONTAINER_SHELL=(
  docker exec
  -it
  -e NET_IF="${NET_IF:-}"
  -w "$CONTAINER_WS"
  "$CONTAINER_NAME"
  bash
)

if ! docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  echo "[enter.sh]: Container $CONTAINER_NAME does not exist. Run docker/run.sh first."
  exit 1
fi

if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" = "true" ]; then
  echo "[enter.sh]: Container $CONTAINER_NAME is running. Opening a shell."
  exec "${CONTAINER_SHELL[@]}"
fi

echo "[enter.sh]: Container $CONTAINER_NAME is stopped. Starting it before opening a shell."
docker start "$CONTAINER_NAME" >/dev/null
exec "${CONTAINER_SHELL[@]}"
