#!/bin/bash

set -xe

mlirsmith="/workdir/MLIRSmith/build/bin/mlirsmith"
target_binary="/workdir/circt/build/bin/circt-opt"
oracle="/workdir/circt/build/bin/circt-opt --mlir-print-op-generic --allow-unregistered-dialect %inputpath"
association_file="/workdir/mlir-eval/circt/dialect-associations.json"  # selection is set to random since mlirsmith doesn't generate CIRCT dialects

# Clean
gen_cleaned_dir="/workdir/mlir-eval/mlirsmith/gen-clean"

# Eval
eval_dir="/workdir/mlir-eval/circt/mlirsmith"
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