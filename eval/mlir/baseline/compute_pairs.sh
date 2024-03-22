#!/bin/bash

set -e

input_dir="/workdir/mlir-seeds/seeds"
output_path="/workdir/mlir-eval/mlir/baseline/diversity.go.json"
oracle="/workdir/llvm-project/build/bin/mlir-opt --mlir-print-op-generic --allow-unregistered-dialect %inputpath"

computepairs -w 32 -b 1 --mlir-opt-path /workdir/llvm-project/build/bin/mlir-opt -o $output_path $input_dir
