#!/bin/bash

mlirsmith="/workdir/MLIRSmith/build/bin/mlirsmith"
target_binary="/workdir/llvm-project/build/bin/mlir-opt"
oracle="/workdir/llvm-project/build/bin/mlir-opt --mlir-print-op-generic --allow-unregistered-dialect %inputpath"

eval_dir="/workdir/mlir-eval/mlirsmith"
log_dir="$eval_dir"
generate_dir="$eval_dir/gen"
gen_cleaned_dir="$eval_dir/gen-clean"
gen_filtered_dir="$eval_dir/gen-filter"
diversity_path="$eval_dir/diversity.json"


if [ -d $eval_dir ]; then
    echo "Directory $eval_dir already exists. Exiting..."
    exit 1
fi

mkdir -p $eval_dir

source ./funcs.sh

generate_test_cases
clean_test_cases
filter_inputs
compute_pairs