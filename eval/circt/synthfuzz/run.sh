#!/bin/bash

set -e
set -x

### Generation Settings ###
count=720000
depth=100
original_seed_pop_dir="/workdir/circt-seeds/trees"
generator_code_dir="/synthfuzz/eval/circt/mlirgen"
disabled_strategies="--no-generate --no-recombine --no-mutate"
mutation_config="/synthfuzz/eval/circt/synthfuzz/mutation_config.toml"
insert_patterns=/synthfuzz/eval/circt/mlirgen/insert_patterns.pkl
context_options="--k-ancestors=4 --l-siblings=4 --r-siblings=4"

### Evaluation Settings ###
target_binary="/workdir/circt/build/bin/circt-opt"
oracle="/workdir/circt/build/bin/circt-opt --mlir-print-op-generic --allow-unregistered-dialect %inputpath"
association_file=/workdir/mlir-eval/circt/dialect-associations.json
max_options=5

### Save Data Settings ###
temp_dir="/tmp/synthfuzz-eval"
eval_dir=/workdir/mlir-eval/circt/synthfuzz

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