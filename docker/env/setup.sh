#!/usr/bin/env bash

if [ -z "${NET_IF:-}" ]; then
  echo "NET_IF is not set. Export NET_IF before sourcing this file." >&2
  return 1 2>/dev/null || exit 1
fi

source /opt/ros/jazzy/setup.bash

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="<CycloneDDS><Domain><General><Interfaces><NetworkInterface name=\"${NET_IF}\" priority=\"default\" multicast=\"default\" /></Interfaces></General></Domain></CycloneDDS>"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/install/setup.bash"

echo "Set CycloneDDS NetworkInterface to ${NET_IF}"
