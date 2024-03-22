#!/bin/bash

set -e
set -x

SCRIPT_PATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd "$SCRIPT_PATH" || exit

source ../common_paths.sh

### Generation Settings ###
count=10100
depth=100
original_seed_pop_dir="/workdir/onnx-mlir-seeds/trees"
generator_code_dir="/synthfuzz/eval/onnx/mlirgen"

### Evaluation Settings ###
target_binary="$mlir_opt_path"
oracle="$mlir_opt_path --mlir-print-op-generic --allow-unregistered-dialect %inputpath"
association_file=$proj_eval_dir/dialect-associations.json
max_options=5

### Save Data Settings ###
temp_dir="/tmp/synthfuzz-eval"
eval_dir=$proj_eval_dir/grammarinator

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
diversity_path=$eval_dir/diversity.go.json

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
