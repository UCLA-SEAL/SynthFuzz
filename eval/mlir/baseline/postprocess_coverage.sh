#!/bin/bash

target_binary=/workdir/llvm-project/build/bin/mlir-opt

echo Accumulating coverage
python -m mlirmut.scripts.accumulate_cov \
    /workdir/mlir-eval/mlir/baseline/batch \
    /workdir/mlir-eval/mlir/baseline/cumulative \
    --unnumbered

echo Exporting
python -m mlirmut.scripts.export_cov_summary \
    /workdir/mlir-eval/mlir/baseline/cumulative \
    /workdir/mlir-eval/mlir/baseline/cov-summary \
    --target-binary $target_binary \
    --timeout 200 # export takes much longer than usual for mlir-opt