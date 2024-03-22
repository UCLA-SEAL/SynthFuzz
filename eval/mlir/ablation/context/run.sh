#!/bin/bash

set -ex

### Generation Settings ###
count=10000
depth=100
original_seed_pop_dir="/workdir/mlir-seeds/trees"
disabled_strategies="--no-generate --no-recombine --no-mutate"
generator_code_dir="/synthfuzz/eval/mlir/mlirgen"
mutation_config="/synthfuzz/eval/mlir/ablation/with_blacklist.toml"
insert_patterns=/synthfuzz/eval/mlir/mlirgen/insert_patterns.pkl

### Evaluation Settings ###
target_binary="/workdir/llvm-project/build/bin/mlir-opt"
oracle="/workdir/llvm-project/build/bin/mlir-opt --mlir-print-op-generic --allow-unregistered-dialect %inputpath"

### Save Data Settings ###
temp_dir="/tmp/synthfuzz-ablation-eval"
parent_eval_dir=/workdir/mlir-eval/mlir-ablation/context

source ./funcs.sh

fullrun() {
    eval_dir="$parent_eval_dir/k$k-l$l-r$r"
    context_options="--k-ancestors=$k --l-siblings=$l --r-siblings=$r"
    set_eval_vars $eval_dir

    if [ -d $eval_dir ]; then
        echo "Directory $eval_dir already exists. Exiting..."
        exit 1
    fi

    generate_test_cases
    eval_test_cases
    postprocess_cov
    compute_pairs
}

# taguichi array
k=0; l=0; r=0
fullrun
k=0; l=2; r=2
fullrun
k=0; l=4; r=4
fullrun

k=2; l=0; r=2
fullrun
k=2; l=2; r=4
fullrun
k=2; l=4; r=0
fullrun

k=4; l=0; r=4
fullrun
k=4; l=2; r=0
fullrun
k=4; l=4; r=2
fullrun