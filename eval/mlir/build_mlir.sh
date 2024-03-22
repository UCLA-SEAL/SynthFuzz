#!/bin/bash

set -e

#COMMIT_SHA="c7aa98558cf354ee76c664267727e41585a50a2f"
#COMMIT_SHA="ab5eae01646e2a83356ec8fe300bf727dadc87dd"
COMMIT_SHA="701d804cdb6944fbb2d4519c1f334425b3a38677"

WORKDIR=/workdir
cd $WORKDIR

if [ ! -d "llvm-project" ]; then
    echo "Cloning LLVM..."
    git clone https://github.com/llvm/llvm-project.git
fi

cd llvm-project

# Check if the specific commit is already checked out
if [ "$(git rev-parse HEAD)" != "$COMMIT_SHA" ]; then
    echo "Checking out specific commit ($COMMIT_SHA)..."
    git checkout $COMMIT_SHA
fi

if [ ! -d "build" ]; then
    mkdir build
fi
cd build

echo "Building MLIR..."
cmake -G Ninja ../llvm \
    -DLLVM_ENABLE_PROJECTS=mlir \
    -DLLVM_BUILD_EXAMPLES=ON \
    -DLLVM_TARGETS_TO_BUILD="Native;NVPTX;AMDGPU" \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON \
    -DLLVM_USE_LINKER=lld \
    -DCMAKE_C_COMPILER=clang \
    -DCMAKE_CXX_COMPILER=clang++ \
    -DCMAKE_CXX_FLAGS="-fprofile-instr-generate -fcoverage-mapping"
cmake --build . --target check-mlir -j 16
