#!/bin/bash

python -m mlirmut.scripts.find_seeds \
	/workdir/llvm-project \
	/workdir/mlir-seeds \
	--exclude-path /workdir/llvm-project/build \
	--mlir-opt-path /workdir/llvm-project/build/bin/mlir-opt \
	--grammar /synthfuzz/eval/mlir/mlir_2023.g4 \
	--start-rule start_rule
