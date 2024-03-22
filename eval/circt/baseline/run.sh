#!/bin/bash

set -e
set -x

### Evaluation Settings ###
target_binary="/workdir/circt/build/bin/circt-opt"
oracle="/workdir/circt/build/bin/circt-opt --mlir-print-op-generic --allow-unregistered-dialect %inputpath"
association_file=/workdir/mlir-eval/circt/dialect-associations.json
max_options=5

### Save Data Settings ###
temp_dir="/tmp/synthfuzz-eval"
eval_dir=/workdir/mlir-eval/circt/baseline

# Generate
eval_input_dir=/workdir/circt-seeds/seeds
eval_log_dir=$eval_dir/eval-log
cov_batch_dir=$eval_dir/cov-batch
eval_batch_size=50

# Postprocess Coverage
cov_cumulative_dir=$eval_dir/cov-cumulative
cov_summary_dir=$eval_dir/cov-summary

# Compute Diversity
pair_input_dir=$eval_input_dir
diversity_path=$eval_dir/diversity.go.json

if [ -d $eval_dir ]; then
    echo "Directory $eval_dir already exists. Exiting..."
    exit 1
fi

source ./funcs.sh

eval_test_cases
postprocess_cov
compute_pairs
