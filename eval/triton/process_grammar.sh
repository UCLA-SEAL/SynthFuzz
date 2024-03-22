#!/bin/bash

mkdir -p /synthfuzz/eval/triton/mlirgen

python -m mlirmut.synthfuzz.process \
	/synthfuzz/eval/triton/mlir_2023.g4 \
	--rule start_rule \
	-o /synthfuzz/eval/triton/mlirgen

