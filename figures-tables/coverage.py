import os
import json
from tqdm import tqdm
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import click

def load_values(data_dir, cov_type="branches", value="percent", limit=None):
    indicies = []
    values = []
    file_names = os.listdir(data_dir)
    file_numbers = [int(name.split(".")[0]) for name in file_names]
    file_numbers_names = sorted(zip(file_numbers, file_names))
    if limit:
        file_numbers_names = file_numbers_names[:limit]
    print(file_numbers_names)
    for number, name in tqdm(file_numbers_names):
        filepath = os.path.join(data_dir, name)
        with open(filepath) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue
        indicies.append(number)
        values.append(data["data"][0]["totals"][cov_type][value])
    return indicies, values

value_type = "covered"
total_time = 2*60*60
def load_and_format(cov_dir, name, value_type=value_type, total_time=total_time):
    indices, values = load_values(
        cov_dir, cov_type="branches", value=value_type
    )
    time_interval = total_time / len(indices)
    time_points = [i * time_interval for i in range(len(indices))]
    df = pd.DataFrame({"time": time_points, value_type: values})
    df["Fuzzer"] = name
    return df
cache_path = "/synthfuzz/data/coverage/mlir_cov.parquet"
if os.path.exists(cache_path):
    mlir_cov = pd.read_parquet(cache_path)
else:
    with open("/workdir/mlir-eval/mlir/baseline/cov-summary/33.profdata.json") as f:
        data = json.load(f)
    baseline_cov = data["data"][0]["totals"]["branches"]["covered"]
    mlir_cov = pd.concat([
        load_and_format("/workdir/mlir-eval/mlir/synthfuzz/cov-summary", "SynthFuzz"),
        load_and_format("/workdir/mlir-eval/mlir/grammarinator/cov-summary", "Grammarinator"),
        load_and_format("/workdir/mlir-eval/mlir/mlirsmith/cov-summary", "MLIRSmith"),
        load_and_format("/workdir/mlir-eval/mlir/neuri/cov-summary", "NeuRI"),
        pd.DataFrame({"Fuzzer": ["Baseline"]*2, "time": [0, 7000], "covered": [baseline_cov, baseline_cov]}),
    ])
    mlir_cov.to_parquet(cache_path)

cache_path = "/synthfuzz/data/coverage/circt_cov.parquet"
if os.path.exists(cache_path):
    circt_cov = pd.read_parquet(cache_path)
else:
    with open("/workdir/mlir-eval/circt/baseline/cov-summary/7.profdata.json") as f:
        data = json.load(f)
    baseline_cov = data["data"][0]["totals"]["branches"]["covered"]
    circt_cov = pd.concat([
        load_and_format("/workdir/mlir-eval/circt/synthfuzz/cov-summary", "SynthFuzz"),
        load_and_format("/workdir/mlir-eval/circt/grammarinator/cov-summary", "Grammarinator"),
        load_and_format("/workdir/mlir-eval/circt/mlirsmith/cov-summary", "MLIRSmith"),
        load_and_format("/workdir/mlir-eval/circt/neuri/cov-summary", "NeuRI"),
        pd.DataFrame({"Fuzzer": ["Baseline"]*2, "time": [0, total_time], "covered": [baseline_cov, baseline_cov]}),
    ])
    circt_cov.to_parquet(cache_path)

cache_path = "/synthfuzz/data/coverage/onnx_cov.parquet"
if os.path.exists(cache_path):
    onnx_cov = pd.read_parquet(cache_path)
else:
    with open("/workdir/mlir-eval/onnx/baseline/cov-summary/37.profdata.json") as f:
        data = json.load(f)
    baseline_cov = data["data"][0]["totals"]["branches"]["covered"]
    onnx_cov = pd.concat([
        load_and_format("/workdir/mlir-eval/onnx/synthfuzz/cov-summary", "SynthFuzz"),
        load_and_format("/workdir/mlir-eval/onnx/grammarinator/cov-summary", "Grammarinator"),
        load_and_format("/workdir/mlir-eval/onnx/mlirsmith/cov-summary", "MLIRSmith"),
        load_and_format("/workdir/mlir-eval/onnx/neuri/cov-summary", "NeuRI"),
        pd.DataFrame({"Fuzzer": ["Baseline"]*2, "time": [0, total_time], "covered": [baseline_cov, baseline_cov]}),
    ])
    onnx_cov.to_parquet(cache_path)

cache_path = "/synthfuzz/data/coverage/triton_cov.parquet"
if os.path.exists(cache_path):
    triton_cov = pd.read_parquet(cache_path)
else:
    with open("/workdir/mlir-eval/triton/baseline/cov-summary/0.profdata.json") as f:
        data = json.load(f)
    baseline_cov = data["data"][0]["totals"]["branches"]["covered"]
    triton_cov = pd.concat([
        load_and_format("/workdir/mlir-eval/triton/synthfuzz/cov-summary", "SynthFuzz"),
        load_and_format("/workdir/mlir-eval/triton/grammarinator/cov-summary", "Grammarinator"),
        load_and_format("/workdir/mlir-eval/triton/mlirsmith/cov-summary", "MLIRSmith"),
        load_and_format("/workdir/mlir-eval/triton/neuri/cov-summary", "NeuRI"),
        pd.DataFrame({"Fuzzer": ["Baseline"]*2, "time": [0, total_time], "covered": [baseline_cov, baseline_cov]}),
    ])
    triton_cov.to_parquet(cache_path)

fig, axes = plt.subplots(1, 4, figsize=(3*4.5, 3))  # Add extra space for the legend
axes = axes.flatten()

def plot_cov(cov, ax, name, legend=False):
    # rename Baseline to Seeds Only
    cov["Fuzzer"][cov["Fuzzer"] == "Baseline"] = "Seed Test Cases"
    sns.lineplot(
        x="time", y=value_type, data=cov, hue="Fuzzer", style="Fuzzer", markers=False, ax=ax,
        legend=legend
    )
    ax.grid()
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("# Branches Covered")
    ax.set_title(name)

plot_cov(mlir_cov, axes[0], "P1 (mlir-opt)")
plot_cov(onnx_cov, axes[1], "P2 (onnx-mlir-opt)")
plot_cov(triton_cov, axes[2], "P3 (triton-opt)")
plot_cov(circt_cov, axes[3], "P4 (circt-opt)", legend=True)
axes[3].legend(loc="center left", title="Fuzzer", bbox_to_anchor=(1.1, 0.5))

# Adjust the layout to accommodate the legend
plt.tight_layout()
plt.savefig("coverage.png")

def print_cov(cov):
    print(cov.groupby("Fuzzer").max().reset_index()[["Fuzzer", "covered"]])
print("====Raw Coverage=====")
print("=====================")
print("mlir-opt")
print_cov(mlir_cov)
print("============")
print("onnx-mlir-opt")
print_cov(onnx_cov)
print("============")
print("triton-opt")
print_cov(triton_cov)
print("============")
print("circt-opt")
print_cov(circt_cov)

def compute_diff(cov):
    compare_with = ["Grammarinator", "MLIRSmith", "NeuRI", "Seed Test Cases"]
    diffs = dict()
    for fuzzer in compare_with:
        synth_covered = cov.groupby("Fuzzer").max().loc["SynthFuzz"]["covered"]
        other_covered = cov.groupby("Fuzzer").max().loc[fuzzer]["covered"]
        percent_diff = synth_covered / other_covered
        print(f"Synthfuzz v. {fuzzer}: {percent_diff}")
        diffs[fuzzer] = percent_diff
    return diffs
print("====SynthFuzz Cov / Other Coverage=====")
print("=======================================")
print("====mlir-opt=====")
mlir_diffs = compute_diff(mlir_cov)
print(mlir_diffs)
print("====onnx-mlir-opt=====")
onnx_diffs = compute_diff(onnx_cov)
print(onnx_diffs)
print("====triton-opt=====")
triton_diffs = compute_diff(triton_cov)
print(triton_diffs)
print("====circt-opt=====")
circt_diffs = compute_diff(circt_cov)
print(circt_diffs)