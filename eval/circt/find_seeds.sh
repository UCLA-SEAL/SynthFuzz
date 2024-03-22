#!/bin/bash

python -m mlirmut.scripts.find_seeds \
	/workdir/circt \
	/workdir/circt-seeds \
	--exclude-path /workdir/circt/llvm \
	--exclude-path /workdir/circt/build \
	--mlir-opt-path /workdir/circt/build/bin/circt-opt \
	--grammar /synthfuzz/eval/circt/mlir_2023.g4 \
	--start-rule start_rule
