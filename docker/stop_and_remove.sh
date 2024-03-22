#!/bin/bash

set -e

SCRIPT_DIR=$(dirname $(realpath "${BASH_SOURCE}"))
cd "$SCRIPT_DIR"

. .env

docker stop $ENV_IMG_NAME
docker rm $ENV_IMG_NAME
