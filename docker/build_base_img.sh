#!/bin/bash

set -ex

SCRIPT_DIR=$(dirname $(realpath "${BASH_SOURCE}"))
REPO_DIR=$(dirname $SCRIPT_DIR)
cd "$SCRIPT_DIR"

. .env

DOCKERFILE_PATH="$SCRIPT_DIR/Dockerfile.base"

docker build "$REPO_DIR" \
	-f "$DOCKERFILE_PATH" \
	-t benlimpa/synthfuzz_base:v1