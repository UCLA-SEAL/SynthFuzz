#!/bin/bash

parent_dir="/workdir/mlir-eval/baseline-eval"
input_dir="/workdir/mlir-seeds/seeds"
batch_dir="$parent_dir/batch"
profdata_path="$parent_dir/coverage.profdata"
log_dir="$parent_dir/eval-log"
temp_dir="/tmp/synthfuzz-eval"
mkdir -p $log_dir
mkdir -p $temp_dir
mkdir -p $batch_dir

target_binary="/workdir/llvm-project/build/bin/mlir-opt"

python -m mlirmut.scripts.mlir_test_harness \
    $input_dir \
    $profdata_path \
    $log_dir \
    "$target_binary" \
    --batch-dir $batch_dir \
    --temp-dir $temp_dir \
    --batch-size 50 \
    --seed 2024 \
    --merge-batches
