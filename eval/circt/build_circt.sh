#!/bin/bash

set -e
set -x

TARGET_DIR=/workdir/circt
CIRCT_SHA="9a78825b45566cf0abbdb6650ccd3954b2545927"

cd /workdir

if [ ! -d "$TARGET_DIR" ]; then
   echo "Cloning CIRCT..."
   git clone https://github.com/llvm/circt.git "$TARGET_DIR"
fi

pushd "$TARGET_DIR"

# Check if the specific commit is already checked out
if [ "$(git rev-parse HEAD)" != "$CIRCT_SHA" ]; then
   echo "Checking out specific commit ($CIRCT_SHA)..."
   git checkout $CIRCT_SHA
fi

echo "Updating submodules..."
git submodule update --init --recursive

echo "Building LLVM..."
pushd llvm
   if [ ! -d "build" ]; then
      mkdir build
   fi
   pushd build
      cmake -G Ninja ../llvm \
         -DLLVM_ENABLE_PROJECTS="mlir" \
         -DLLVM_TARGETS_TO_BUILD="X86;RISCV" \
         -DLLVM_ENABLE_ASSERTIONS=ON \
         -DCMAKE_BUILD_TYPE=Release \
         -DCMAKE_C_COMPILER=clang \
         -DCMAKE_CXX_COMPILER=clang++ \
         -DLLVM_ENABLE_LLD=ON
      ninja
   popd
popd

echo "Building CIRCT..."
if [ ! -d "build" ]; then
    mkdir build
fi
pushd build
   cmake -G Ninja .. \
      -DMLIR_DIR=$PWD/../llvm/build/lib/cmake/mlir \
      -DLLVM_DIR=$PWD/../llvm/build/lib/cmake/llvm \
      -DLLVM_ENABLE_ASSERTIONS=ON \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_C_COMPILER=clang \
      -DCMAKE_CXX_COMPILER=clang++ \
      -DLLVM_ENABLE_LLD=ON \
      -DCMAKE_CXX_FLAGS="-fprofile-instr-generate -fcoverage-mapping"
   ninja
popd
popd