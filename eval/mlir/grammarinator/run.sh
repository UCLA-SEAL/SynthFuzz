#!/bin/bash

set -e
set -x

### Generation Settings ###
count=10348
depth=100
original_seed_pop_dir="/workdir/mlir-seeds/trees"
generator_code_dir="/synthfuzz/eval/mlir/mlirgen"

### Evaluation Settings ###
target_binary="/workdir/llvm-project/build/bin/mlir-opt"
oracle="/workdir/llvm-project/build/bin/mlir-opt --mlir-print-op-generic --allow-unregistered-dialect %inputpath"

### Save Data Settings ###
temp_dir="/tmp/synthfuzz-ablation-eval"
eval_dir=/workdir/mlir-eval/mlir/grammarinator

# Generate
working_seed_pop_dir=$eval_dir/seeds
generate_log=$eval_dir/gen.log
generate_dir=$eval_dir/gen
generate_batch_dir=$eval_dir/gen-batch
input_batch_size=2

# Eval
eval_log_dir=$eval_dir/eval-log
cov_batch_dir=$eval_dir/cov-batch
eval_batch_size=10

# Postprocess Coverage
cov_cumulative_dir=$eval_dir/cov-cumulative
cov_summary_dir=$eval_dir/cov-summary

# Compute Diversity
gen_filtered_dir=$eval_dir/gen-filtered
diversity_path=$eval_dir/diversity.json

if [ -d $eval_dir ]; then
    echo "Directory $eval_dir already exists. Exiting..."
    exit 1
fi

source ./funcs.sh

generate_test_cases
batch_test_cases
eval_test_cases
postprocess_cov
compute_pairs