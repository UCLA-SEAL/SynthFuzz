#!/bin/bash

set -e
set -x

### Generation Settings ###
count=10000
depth=100
original_seed_pop_dir="/workdir/mlir-seeds/trees"
disabled_strategies="--no-generate --no-recombine --no-mutate"
generator_code_dir="/synthfuzz/eval/mlir/mlirgen"
mutation_config="/synthfuzz/eval/mlir/ablation/no_config.toml"
insert_patterns=/synthfuzz/eval/mlir/mlirgen/insert_patterns.pkl
context_options="--k-ancestors=4 --l-siblings=4 --r-siblings=4"

### Evaluation Settings ###
target_binary="/workdir/llvm-project/build/bin/mlir-opt"
oracle="/workdir/llvm-project/build/bin/mlir-opt --mlir-print-op-generic --allow-unregistered-dialect %inputpath"

### Save Data Settings ###
eval_dir=/workdir/mlir-eval/mlir-ablation/with-parameters
working_seed_pop_dir=$eval_dir/seeds
generate_log=$eval_dir/gen.log
edit_log_dir=$eval_dir/edit-log
generate_dir=$eval_dir/gen
eval_log_dir=$eval_dir/eval-log
profdata_path="$parent_dir/coverage.profdata"
temp_dir="/tmp/synthfuzz-ablation-eval"
cov_batch_dir=$eval_dir/cov-batch
cov_cumulative_dir=$eval_dir/cov-cumulative
cov_summary_dir=$eval_dir/cov-summary
gen_filtered_dir=$eval_dir/gen-filtered
diversity_path=$eval_dir/diversity.json

if [ -d $eval_dir ]; then
    echo "Directory $eval_dir already exists. Exiting..."
    exit 1
fi

source ./utils.sh

generate_test_cases
eval_test_cases
postprocess_cov
compute_pairs