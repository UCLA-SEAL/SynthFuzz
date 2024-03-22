#!/bin/bash

python -m mlirmut.scripts.find_seeds \
	/workdir/onnx-mlir \
	/workdir/onnx-mlir-seeds \
	--exclude-path /workdir/onnx-mlir/llvm-project \
	--exclude-path /workdir/onnx-mlir/build \
	--mlir-opt-path /workdir/onnx-mlir/build/Debug/bin/onnx-mlir-opt \
	--grammar /synthfuzz/eval/onnx/mlir_2023.g4 \
	--start-rule start_rule
