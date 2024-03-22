#!/bin/bash

set -xe

target_binary="/workdir/llvm-project/build/bin/mlir-opt"
oracle="/workdir/llvm-project/build/bin/mlir-opt --mlir-print-op-generic --allow-unregistered-dialect %inputpath"
association_file="/workdir/mlir-eval/mlir/dialect-associations.json"

# Eval
eval_dir="/workdir/mlir-eval/mlir/neuri"

generate_dir="/workdir/mlir-eval/neuri/mlir"
eval_log_dir="$eval_dir/eval"
cov_batch_dir="$eval_dir/cov-batch"
temp_dir="/tmp/neuri-eval"
eval_batch_size=50
max_options=5

cov_cumulative_dir="$eval_dir/cov-cumulative"
cov_summary_dir="$eval_dir/cov-summary"


if [ -d $eval_dir ]; then
    echo "Directory $eval_dir already exists. Exiting..."
    exit 1
fi

mkdir -p $eval_dir

source ./funcs.sh

eval_test_cases
postprocess_cov