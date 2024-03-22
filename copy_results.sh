#!/bin/bash

set -ex


subjects=("mlir" "onnx" "triton" "circt")
fuzzers=("synthfuzz" "grammarinator" "baseline")

for subject in "${subjects[@]}"; do
    mkdir -p /synthfuzz/data/diversity/$subject
    for fuzzer in "${fuzzers[@]}"; do
        cp /workdir/mlir-eval/$subject/$fuzzer/diversity.go.json /synthfuzz/data/diversity/$subject/$fuzzer.json
    done
done

cp /workdir/mlir-eval/mlirsmith/diversity.go.json /synthfuzz/data/diversity/mlirsmith.json
cp /workdir/mlir-eval/neuri/diversity.go.json /synthfuzz/data/diversity/neuri.json