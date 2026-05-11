#!/bin/bash
set -euo pipefail

IMAGE_NAME="elevation_mapping_cupy:jazzy"
CONTAINER_NAME="elevation_mapping_cupy_jazzy"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONTAINER_WS="/home/ubuntu/workspace"
CONTAINER_REPO="$CONTAINER_WS/src/elevation_mapping_cupy"
CONTAINER_SHELL=(
  docker exec
  -it
  -e NET_IF="${NET_IF:-}"
  -w "$CONTAINER_WS"
  "$CONTAINER_NAME"
  bash
)

# Define environment variables for enabling graphical output for the container.
XSOCK=/tmp/.X11-unix
XAUTH=/tmp/.docker.xauth
if [ ! -f "$XAUTH" ]
then
    touch "$XAUTH"
    xauth_list=$(xauth nlist :0 | sed -e 's/^..../ffff/')
    xauth nlist "$DISPLAY" | sed -e 's/^..../ffff/' | xauth -f "$XAUTH" nmerge -
    chmod a+r "$XAUTH"
fi

#==
# Launch or reuse container
#==

if [ -z "${NET_IF:-}" ]; then
  echo "[run.sh]: NET_IF is not set on the host. Export NET_IF before sourcing /home/ubuntu/workspace/setup.sh inside the container."
else
  echo "[run.sh]: NET_IF=${NET_IF}"
fi

if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" = "true" ]; then
    echo "[run.sh]: Container $CONTAINER_NAME is already running. Opening a new shell."
  else
    echo "[run.sh]: Container $CONTAINER_NAME exists but is stopped. Starting it before opening a shell."
    docker start "$CONTAINER_NAME" >/dev/null
  fi
  "${CONTAINER_SHELL[@]}"
  echo "[run.sh]: Docker terminal closed."
  exit 0
fi

RUN_COMMAND=(
  docker run
  -d
  --name "$CONTAINER_NAME"
  --volume="$XSOCK:$XSOCK:rw"
  --volume="$XAUTH:$XAUTH:rw"
  --env="QT_X11_NO_MITSHM=1"
  --env="TERM=xterm-256color"
  --env="COLORTERM=truecolor"
  --env="XAUTHORITY=$XAUTH"
  --env="DISPLAY=$DISPLAY"
  -e NET_IF
  --ulimit rtprio=99
  --cap-add=sys_nice
  --privileged
  --net=host
  -e "HOST_USERNAME=$(whoami)"
  -e "WS=$CONTAINER_WS"
  -v "$REPO_ROOT:$CONTAINER_REPO"
  -w "$CONTAINER_WS"
  --gpus all
  "$IMAGE_NAME"
  bash -lc 'sudo mkdir -p "$WS/src" && sudo chown "$(id -u):$(id -g)" "$WS" "$WS/src" && tail -f /dev/null'
)
echo -e "[run.sh]: \e[1;32mThe final run command is\n\e[0;35m$(printf '%q ' "${RUN_COMMAND[@]}")\e[0m."
"${RUN_COMMAND[@]}"
"${CONTAINER_SHELL[@]}"
echo -e "[run.sh]: \e[1;32mDocker terminal closed.\e[0m"
