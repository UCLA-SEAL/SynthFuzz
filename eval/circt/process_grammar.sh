#!/bin/bash

mkdir -p /synthfuzz/eval/circt/mlirgen

python -m mlirmut.synthfuzz.process \
	/synthfuzz/eval/circt/mlir_2023.g4 \
	--rule start_rule \
	-o /synthfuzz/eval/circt/mlirgen

