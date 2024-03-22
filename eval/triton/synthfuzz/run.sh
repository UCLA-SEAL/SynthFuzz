#!/bin/bash

set -e
set -x

SCRIPT_PATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd "$SCRIPT_PATH" || exit

source ../common_paths.sh

### Generation Settings ###
count=720000
depth=100
original_seed_pop_dir="/workdir/triton-seeds/trees"
generator_code_dir="/synthfuzz/eval/triton/mlirgen"
disabled_strategies="--no-generate --no-recombine --no-mutate"
mutation_config="/synthfuzz/eval/triton/synthfuzz/mutation_config.toml"
insert_patterns=/synthfuzz/eval/triton/mlirgen/insert_patterns.pkl
context_options="--k-ancestors=4 --l-siblings=4 --r-siblings=4"

### Evaluation Settings ###
target_binary="$mlir_opt_path"
oracle="$mlir_opt_path --mlir-print-op-generic --allow-unregistered-dialect %inputpath"
association_file=/workdir/mlir-eval/triton/dialect-associations.json
max_options=5

### Save Data Settings ###
temp_dir="/tmp/synthfuzz-eval"
eval_dir=/workdir/mlir-eval/triton/synthfuzz

# Generate
working_seed_pop_dir=$eval_dir/seeds
generate_log=$eval_dir/gen.log
generate_dir=$eval_dir/gen
generate_batch_dir=$eval_dir/gen-batch
input_batch_size=50  # approx 14400 invocations

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
