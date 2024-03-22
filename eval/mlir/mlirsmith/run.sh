#!/bin/bash

set -xe

mlirsmith="/workdir/MLIRSmith/build/bin/mlirsmith"
target_binary="/workdir/llvm-project/build/bin/mlir-opt"
oracle="/workdir/llvm-project/build/bin/mlir-opt --mlir-print-op-generic --allow-unregistered-dialect %inputpath"
association_file="/workdir/mlir-eval/mlir/dialect-associations.json"


# Clean
gen_cleaned_dir="/workdir/mlir-eval/mlirsmith/gen-clean"

# Eval
eval_dir="/workdir/mlir-eval/mlir/mlirsmith"
eval_log_dir="$eval_dir/eval"
cov_batch_dir="$eval_dir/cov-batch"
cov_cumulative_dir="$eval_dir/cov-cumulative"
cov_summary_dir="$eval_dir/cov-summary"
temp_dir="/tmp/mlirsmith-eval"
max_options=5
eval_batch_size=1



if [ -d $eval_dir ]; then
    echo "Directory $eval_dir already exists. Exiting..."
    exit 1
fi

mkdir -p $eval_dir

source ./funcs.sh

eval_test_cases
postprocess_cov