#!/bin/bash
set -euo pipefail

CONTAINER_NAME="elevation_mapping_cupy_jazzy"

if ! docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  echo "[stop.sh]: Container $CONTAINER_NAME does not exist."
  exit 0
fi

if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" != "true" ]; then
  echo "[stop.sh]: Container $CONTAINER_NAME is already stopped."
  exit 0
fi

echo "[stop.sh]: Stopping container $CONTAINER_NAME."
docker stop "$CONTAINER_NAME" >/dev/null
echo "[stop.sh]: Container $CONTAINER_NAME stopped."
