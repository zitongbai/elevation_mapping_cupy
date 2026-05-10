#!/bin/bash
IMAGE_NAME="elevation_mapping_cupy:jazzy"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONTAINER_WS="/home/ubuntu/workspace"
CONTAINER_REPO="$CONTAINER_WS/src/elevation_mapping_cupy"

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
# Launch container
#==

# Launch a container from the prebuilt image with only this repository mounted.
echo "---------------------"
RUN_COMMAND=(
  docker run
  --volume="$XSOCK:$XSOCK:rw"
  --volume="$XAUTH:$XAUTH:rw"
  --env="QT_X11_NO_MITSHM=1"
  --env="TERM=xterm-256color"
  --env="COLORTERM=truecolor"
  --env="XAUTHORITY=$XAUTH"
  --env="DISPLAY=$DISPLAY"
  --ulimit rtprio=99
  --cap-add=sys_nice
  --privileged
  --net=host
  -e "HOST_USERNAME=$(whoami)"
  -e "WS=$CONTAINER_WS"
  -v "$REPO_ROOT:$CONTAINER_REPO"
  -w "$CONTAINER_WS"
  --gpus all
  -it "$IMAGE_NAME"
  bash -lc 'sudo mkdir -p "$WS/src" && sudo chown "$(id -u):$(id -g)" "$WS" "$WS/src" && exec bash'
)
echo -e "[run.sh]: \e[1;32mThe final run command is\n\e[0;35m$(printf '%q ' "${RUN_COMMAND[@]}")\e[0m."
"${RUN_COMMAND[@]}"
echo -e "[run.sh]: \e[1;32mDocker terminal closed.\e[0m"
#   --entrypoint=$ENTRYPOINT \
