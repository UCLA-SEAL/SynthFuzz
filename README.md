# Requirements

Before running this artifact, please install Docker ([Installation Instructions](https://docs.docker.com/engine/install/)).
Please also ensure that this artifact is extracted to a directory whose absolute path does not contain spaces.

1. Build the docker image by running `./docker/build.sh`
2. Start the container by running `./docker/run_default.sh`
3. Enter the container by running `./docker/attach.sh`. All commands after this point should be run inside the container.

# Generating Figures and Tables

The post-processed branch and dialect pair coverage has been included with this artifact for convenience.
If you would like to reproduce the results from scratch delete the `synthfuzz-icse2025/data` directory and follow the directions in the *Running Experiments and Collecting Coverage From Scratch* section before continuing with this section. Note that running the experiments from scratch may take several days depending on your machine.

## RQ1: Branch Coverage
*All commands should be run inside the Docker container.*

```bash
cd /synthfuzz
python figures-tables/coverage.py
```

## RQ2: Dialect Pair Coverage
*All commands should be run inside the Docker container.*

```bash
cd /synthfuzz
python figures-tables/diversity.py
```

## RQ3: Context-based Location Selection
*All commands should be run inside the Docker container.*

```bash
cd /synthfuzz
python figures-tables/ablation-context.py
```

## RQ4: Parameterization
*All commands should be run inside the Docker container.*

```bash
cd /synthfuzz
python figures-tables/ablation-params.py
```

# Running Experiments and Collecting Coverage:
*All commands should be run inside the Docker container.*

1. Compile each subject program:
```bash
cd /synthfuzz/eval
# build mlir-opt
./mlir/build_mlir.sh
# build onnx-mlir-opt
./onnx/build_onnx_mlir.sh
# build triton-opt
./triton/build.sh
# build circt-opt
./circt/build_circt.sh
```
2. Extract seed test cases from each subject's repositories:
```bash
cd /synthfuzz/eval
./mlir/find_seeds.sh
./onnx/find_seeds.sh
./triton/find_seeds.sh
./circt/find_seeds.sh
```

3. *Optional* only if you want to evaluate against NeuRI: For this step only, NeuRI needs to be run in its own container. 
Run the following *outside* the synthfuzz-artifact-icse2025 container:
```bash
cd synthfuzz-icse2025/eval/neuri
./start_docker.sh
./gen_indocker.sh  # inside the neuri-artifact container
```
Now returning to the synthfuzz-artifact-icse2025 container:
```bash
cd /synthfuzz/eval/neuri
python copy_models.py
python tf_to_onnx.py
python onnx_to_mlir.py
python onnx_to_onnx_mlir.py
```
3. Run each experiment:
```bash
# install computepairs
cd /synthfuzz/computepairs
go install

# ablation
cd /synthfuzz/eval/mlir/ablation/context && ./run.sh
cd /synthfuzz/eval/mlir/ablation && ./no_parameters.sh
cd /synthfuzz/eval/mlir/ablation && ./with_parameters.sh

# Coverage experiments

cd /synthfuzz/eval/mlirsmith && ./run.sh
cd /synthfuzz/eval/mlir/baseline && ./run.sh
cd /synthfuzz/eval/mlir/synthfuzz && ./run.sh
cd /synthfuzz/eval/mlir/grammarinator && ./run.sh
cd /synthfuzz/eval/mlir/mlirsmith && ./run.sh

cd /synthfuzz/eval/onnx/baseline && ./run.sh
cd /synthfuzz/eval/onnx/synthfuzz && ./run.sh
cd /synthfuzz/eval/onnx/grammarinator && ./run.sh
cd /synthfuzz/eval/onnx/mlirsmith && ./run.sh

cd /synthfuzz/eval/triton/baseline && ./run.sh
cd /synthfuzz/eval/triton/synthfuzz && ./run.sh
cd /synthfuzz/eval/triton/grammarinator && ./run.sh
cd /synthfuzz/eval/triton/mlirsmith && ./run.sh

cd /synthfuzz/eval/circt/baseline && ./run.sh
cd /synthfuzz/eval/circt/synthfuzz && ./run.sh
cd /synthfuzz/eval/circt/grammarinator && ./run.sh
cd /synthfuzz/eval/circt/mlirsmith && ./run.sh

# Only if step 3 was followed:
cd /synthfuzz/eval/mlir/neuri && ./run.sh
cd /synthfuzz/eval/onnx/neuri && ./run.sh
cd /synthfuzz/eval/triton/neuri && ./run.sh
cd /synthfuzz/eval/circt/neuri && ./run.sh
```