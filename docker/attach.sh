#!/bin/bash

set -e

SCRIPT_DIR=$(dirname $(realpath "${BASH_SOURCE}"))
cd "$SCRIPT_DIR"

. .env

docker exec -it $ENV_IMG_NAME bash
