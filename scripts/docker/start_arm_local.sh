#!/bin/bash

# Local ARM Docker startup (WSL/Linux/macOS). Matches scripts/docker/docker-compose.yml layout.
# Windows Docker Desktop: prefer docker compose -f scripts/docker/docker-compose.yml up --build

IMAGE_NAME="arm-local"
CONTAINER_NAME="arm-local"
ARM_UID="1000"
ARM_GID="1000"
TZ="Europe/Kyiv"
ARM_DEV_MODE="true"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

HOST_HOME="$REPO_ROOT/.arm-docker/home"
HOST_MUSIC="$REPO_ROOT/.arm-docker/home/music"
HOST_LOGS="$REPO_ROOT/.arm-docker/home/logs"
HOST_MEDIA="$REPO_ROOT/.arm-docker/home/media"
HOST_CONFIG="$REPO_ROOT/.arm-docker/config"
HOST_ARM_SRC="$REPO_ROOT/arm"

CPUSET="1,2,3"

mkdir -p "$HOST_HOME" "$HOST_MUSIC" "$HOST_LOGS" "$HOST_MEDIA" "$HOST_CONFIG"

docker run -d \
    -p "8080:8080" \
    -e ARM_UID="$ARM_UID" \
    -e ARM_GID="$ARM_GID" \
    -e TZ="$TZ" \
    -e ARM_DEV_MODE="$ARM_DEV_MODE" \
    -v "$HOST_HOME:/home/arm" \
    -v "$HOST_MUSIC:/home/arm/music" \
    -v "$HOST_LOGS:/home/arm/logs" \
    -v "$HOST_MEDIA:/home/arm/media" \
    -v "$HOST_CONFIG:/etc/arm/config" \
    -v "$HOST_ARM_SRC:/opt/arm/arm" \
    --privileged \
    --restart "unless-stopped" \
    --name "$CONTAINER_NAME" \
    --cpuset-cpus="$CPUSET" \
    "$IMAGE_NAME"
