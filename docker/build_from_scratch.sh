#!/bin/bash

set -ex

SCRIPT_DIR=$(dirname $(realpath "${BASH_SOURCE}"))
REPO_DIR=$(dirname $SCRIPT_DIR)
cd "$SCRIPT_DIR"

. .env

DOCKERFILE_PATH="$SCRIPT_DIR/Dockerfile"

username=$(whoami)
groupname=$username
userid=$(id -u)
groupid=$(id -g)

docker build "$REPO_DIR" \
	-f "$DOCKERFILE_PATH" \
	-t $ENV_IMG_NAME:$ENV_IMG_TAG\
	--build-arg USER="$username" \
	--build-arg GROUP="$groupname" \
	--build-arg USER_ID="$userid" \
	--build-arg GROUP_ID="$groupid"
