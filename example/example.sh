#!/bin/bash

set -e

# Ensure that this is run in the example directory
cd "$(dirname "$0")"

echo Processing Grammar...
if [ ! -d "mlirgen" ]; then
    mkdir mlirgen
    python -m mlirmut.synthfuzz.process mlir_2023.g4 --rule start_rule -o mlirgen
fi

echo Parsing Inputs...
if [ -d "trees" ]; then
    echo Removing existing trees directory...
    rm -rf trees
fi
mkdir trees
grammarinator-parse \
    -r start_rule \
    -i inputs/*.mlir \
    -o trees \
    mlir_2023.g4

echo Running SynthFuzz...
mkdir -p outputs
python -m mlirmut.synthfuzz.generate \
    mlir_2023Generator.mlir_2023Generator \
    -r start_rule \
    -d 100 \
    -o outputs/%d.mlir \
    -n 10 \
    --sys-path mlirgen \
    --population trees \
    --insert-patterns mlirgen/insert_patterns.pkl \
    --mutation-config mutation_config.toml \
    --keep-trees \
    --no-generate --no-recombine --no-mutate \
    --k-ancestors=4 --l-siblings=4 --r-siblings=4
