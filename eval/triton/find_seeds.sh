#!/bin/bash

source ./common_paths.sh

python -m mlirmut.scripts.find_seeds \
	/workdir/triton \
	/workdir/triton-seeds \
	--exclude-path /workdir/triton/python/build \
	--exclude-path /workdir/triton/third_party \
	--mlir-opt-path "$mlir_opt_path" \
	--grammar /synthfuzz/eval/triton/mlir_2023.g4 \
	--start-rule start_rule
