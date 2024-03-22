#!/bin/bash

set -e

if [ ! -d "/workdir" ]; then
   echo "Directory /workdir does not exist. Exiting..."
   exit 1
fi

cd /workdir

# Clear directories if they already exist and --clean flag is set
while (( "$#" )); do
 case "$1" in
   --clean)
     if [ -d "onnx-mlir/build" ]; then
       rm -rf onnx-mlir/build
     fi
     if [ -d "onnx-mlir/llvm-project/build" ]; then
       rm -rf onnx-mlir/llvm-project/build
     fi
     shift
     ;;
   *)
     break
     ;;
 esac
done

if [ -d "onnx-mlir" ]; then
   echo "Directory onnx-mlir already exists. Skipping cloning..."
else
   echo Clone ONNX-MLIR
   git clone https://github.com/onnx/onnx-mlir.git
fi
cd onnx-mlir
git checkout d70cb7ac9e0dd2327413a5c01e225b2efabf8bc4
git submodule update --init --recursive

if [ -d "llvm-project" ]; then
   echo "Directory llvm-project already exists. Skipping cloning..."
else
   echo Clone LLVM
   git clone -n https://github.com/llvm/llvm-project.git
fi
pushd llvm-project
    # Check out a specific branch that is known to work with ONNX-MLIR.
    git checkout b2cdf3cc4c08729d0ff582d55e40793a20bbcdcc
    mkdir -p build
    pushd build
        cmake -G Ninja ../llvm \
        -DLLVM_ENABLE_PROJECTS=mlir \
        -DLLVM_TARGETS_TO_BUILD="host" \
        -DCMAKE_BUILD_TYPE=Release \
        -DLLVM_ENABLE_ASSERTIONS=ON \
        -DLLVM_ENABLE_RTTI=ON \
        -DLLVM_ENABLE_LIBEDIT=OFF \
        -DLLVM_USE_LINKER=lld \
        -DCMAKE_C_COMPILER=clang \
        -DCMAKE_CXX_COMPILER=clang++

        cmake --build .
        cmake --build . --target check-mlir
    popd # build
popd # llvm-project

MLIR_DIR=$(pwd)/llvm-project/build/lib/cmake/mlir

echo Building ONNX-MLIR with coverage...
mkdir -p build
pushd build
    cmake -G Ninja \
            -DONNX_MLIR_ACCELERATORS=NNPA \
            -DMLIR_DIR=${MLIR_DIR} \
            -DLLVM_USE_LINKER=lld \
            -DCMAKE_C_COMPILER=clang \
            -DCMAKE_CXX_COMPILER=clang++ \
            -DCMAKE_CXX_FLAGS="-fprofile-instr-generate -fcoverage-mapping" \
            ..
    cmake --build .
popd

echo Done!