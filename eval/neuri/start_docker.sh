#!/bin/bash

set -xe

workdir=$HOME/workdir/neuri-models

mkdir -p $workdir

docker run \
    -it \
    --name run-neuri \
    -v $workdir:/artifact/gen \
    -v $(pwd):/myscriptdir \
    ganler/neuri-fse23-ae:latest
