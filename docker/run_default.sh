#!/bin/bash

set -e

SCRIPT_DIR=$(dirname $(realpath "${BASH_SOURCE}"))
REPO_DIR=$(dirname "$SCRIPT_DIR")
cd "$SCRIPT_DIR"

. .env

./run.sh "$REPO_DIR/workdir:/workdir" "$REPO_DIR:/synthfuzz" 