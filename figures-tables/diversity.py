import json
import pandas as pd
import yaml
import os
from pathlib import Path

from mlirmut.scripts.compute_pairs import reduce_to_dialect

def compute_unique_pairs(deps):
    pairs = set()
    for name1, name2s in deps.items():
        for name2 in name2s:
            if name1 == name2:
                continue
            pairs.add(frozenset((name1, name2)))
    return pairs

def load_diversity_go(path):
    with open(path, "r") as f:
        diversity = json.load(f)
    return {
        "dialect": {
            "control": compute_unique_pairs(reduce_to_dialect(diversity["control"])),
            "data": compute_unique_pairs(reduce_to_dialect(diversity["data"]))
        },
        "op": {
            "control": compute_unique_pairs(diversity["control"]),
            "data": compute_unique_pairs(diversity["data"])
        }
    }

subjects = ["mlir", "onnx", "triton", "circt"]
seed_fuzzers = ["SynthFuzz", "Grammarinator", "Seeds Only"]
gen_fuzzers = ["MLIRSmith", "NeuRI"]
div_data = dict()

for subject in subjects:
    div_data[subject] = dict()
    for fuzzer in seed_fuzzers:
        fname = "baseline" if fuzzer == "Seeds Only" else fuzzer.lower()
        cache_path = f"/synthfuzz/data/diversity/{subject}/{fname}.json"
        if os.path.exists(cache_path):
            div_data[subject][fuzzer] = load_diversity_go(cache_path)
        else:
            div_data[subject][fuzzer] = load_diversity_go(f"/workdir/mlir-eval/{subject}/{fname}/diversity.go.json")
    for fuzzer in gen_fuzzers:
        fname = fuzzer.lower()
        cache_path = f"/synthfuzz/data/diversity/{fname}.json"
        if os.path.exists(cache_path):
            div_data[subject][fuzzer] = load_diversity_go(cache_path)
        else:
            div_data[subject][fuzzer] = load_diversity_go(f"/workdir/mlir-eval/{fname}/diversity.go.json")

dialects = dict()
dialect_name_dir = Path("/synthfuzz/figures-tables/dialect_names")
with open(dialect_name_dir / "mlir.yml", "r") as f:
    dialects["mlir"] = yaml.safe_load(f)
with open(dialect_name_dir / "onnx.yml", "r") as f:
    dialects["onnx"] = yaml.safe_load(f)
with open(dialect_name_dir / "triton.yml", "r") as f:
    dialects["triton"] = yaml.safe_load(f)
with open(dialect_name_dir / "circt.yml", "r") as f:
    dialects["circt"] = yaml.safe_load(f)

def filter_name(name: str, dialects: list[str]):
    if "." not in name:
        return False
    dialect_name = name.split(".")[0]
    if dialect_name not in dialects:
        return False
    return True

def filter_op_pairs(pairs: set, dialects: list[str]):
    new_pairs = set()
    for pair in pairs:
        name1, name2 = pair
        if filter_name(name1, dialects) and filter_name(name2, dialects):
            new_pairs.add(pair)
    return new_pairs

def derive_dialect_pairs(op_pairs):
    dialect_pairs = set()
    for name1, name2 in op_pairs:
        dialect1, dialect2 = name1.split(".")[0], name2.split(".")[0]
        if dialect1 == dialect2:
            continue
        dialect_pairs.add(frozenset((dialect1, dialect2)))
    return dialect_pairs

def filter_all(full_pairs, dialects):
    op_control_pairs = filter_op_pairs(full_pairs["op"]["control"], dialects)
    op_data_pairs = filter_op_pairs(full_pairs["op"]["data"], dialects)
    return {
        "dialect": {
            "control": derive_dialect_pairs(op_control_pairs),
            "data": derive_dialect_pairs(op_data_pairs)
        },
        "op": {
            "control": op_control_pairs,
            "data": op_data_pairs
        }
    }

for subject, data_by_fuzzer in div_data.items():
    for fuzzer, data in data_by_fuzzer.items():
        div_data[subject][fuzzer] = filter_all(data, dialects[subject])

def data_to_df(data, subject):
    df_data = {
        "Subject": [],
        "Fuzzer": [],
        "Measure": [],
        "Pair Type": [],
        "Count": [],
    }
    for name, pairs in data.items():
        for pair_type in ["dialect"]:#, "op"]:
            unique_entries = set()
            for dep_type in ["control", "data"]:
                df_data["Subject"].append(subject)
                df_data["Fuzzer"].append(name)
                df_data["Measure"].append(f"{dep_type} pairs")
                df_data["Pair Type"].append(pair_type)
                df_data["Count"].append(len(pairs[pair_type][dep_type]))
                for pair in pairs[pair_type][dep_type]:
                    for entry in pair:
                        unique_entries.add(entry)
            df_data["Subject"].append(subject)
            df_data["Fuzzer"].append(name)
            df_data["Measure"].append("\\# dialects")
            df_data["Pair Type"].append(pair_type)
            df_data["Count"].append(len(unique_entries))


    return pd.DataFrame(df_data)

dfs = {
    subject: data_to_df(div_data[subject], f"P{idx+1} ({subject})")
    for idx, subject in enumerate(subjects)
}

def display_df(df):
    ddf = pd.DataFrame({
        #"# Dialects": df["Count"],
        "Count": df["Count"]
    })
    ddf.index = pd.MultiIndex.from_frame(df[["Fuzzer", "Measure", "Subject"]])
    return ddf
all_dfs = pd.concat(dfs.values())
ddf = display_df(all_dfs).unstack().unstack()
ddf = ddf.reindex(["SynthFuzz", "Seeds Only", "Grammarinator", "MLIRSmith", "NeuRI"])
print(ddf)

print("====SynthFuzz Control/Data Diversity / Other Control/Data Diversity=====")
control_diffs = dict()
data_diffs = dict()
fuzzers_to_compare = ["Grammarinator", "MLIRSmith", "NeuRI", "Seeds Only"]
for subject, df in dfs.items():
    synthfuzz_filter = df["Fuzzer"] == "SynthFuzz"
    control_pair_filter = df["Measure"] == "control pairs"
    data_pair_filter = df["Measure"] == "data pairs"
    control_diffs[subject] = dict()
    data_diffs[subject] = dict()
    for fuzzer in fuzzers_to_compare:
        fuzzer_filter = df["Fuzzer"] == fuzzer
        control_diffs[subject][f"SynthFuzz vs {fuzzer}"] = df[synthfuzz_filter & control_pair_filter]["Count"].iloc[0] / df[fuzzer_filter & control_pair_filter]["Count"].iloc[0]
        data_diffs[subject][f"SynthFuzz vs {fuzzer}"] = df[synthfuzz_filter & data_pair_filter]["Count"].iloc[0] / df[fuzzer_filter & data_pair_filter]["Count"].iloc[0]
    
    print(f"===={subject}=====")
    for compare_name in control_diffs[subject].keys(): 
        print(f"{compare_name}: C: {control_diffs[subject][compare_name]:.4f} D: {data_diffs[subject][compare_name]:.4f}")

total_diffs = dict()
for ptype, diffs in zip(["control", "data"], [control_diffs, data_diffs]):
    total_diffs[ptype] = {
        "Grammarinator": 0,
        "MLIRSmith": 0,
        "NeuRI": 0,
        "Seeds Only": 0,
        "Min": 0,
    }
    for subject, diff in diffs.items():
        if subject == "iree":
            print("skip iree")
            continue
        min_diff = min(diff.values())
        total_diffs[ptype]["Min"] += min_diff / 4
        for against in total_diffs[ptype].keys():
            if against == "Min":
                continue
            total_diffs[ptype][against] += diff[f"SynthFuzz vs {against}"] / 4
print("=====Average Diversity Difference======")
for ptype in ["control", "data"]:
    print(f"====={ptype}=====")
    for against, proportion in total_diffs.items():
        print(f"SynthFuzz v. {against}: {proportion}")

def total_pair_df(data, subject):
    df_data = {
        "Subject": [],
        "Fuzzer": [],
        "Count": [],
    }
    for name, pairs in data.items():
        for pair_type in ["dialect"]:#, "op"]:
            unique_pairs = set()
            for dep_type in ["control", "data"]:
                for pair in pairs[pair_type][dep_type]:
                    unique_pairs.add(pair)
            df_data["Subject"].append(subject)
            df_data["Fuzzer"].append(name)
            df_data["Count"].append(len(unique_pairs))
    return pd.DataFrame(df_data)
total_dfs = {
    subject: total_pair_df(div_data[subject], f"P{idx+1} ({subject})")
    for idx, subject in enumerate(subjects)
}

print("====SynthFuzz Control+Data Diversity / Other Control+Data Diversity=====")
diffs = dict()
fuzzers_to_compare = ["Grammarinator", "MLIRSmith", "NeuRI", "Seeds Only"]
for subject, df in total_dfs.items():
    diffs[subject] = {
        f"SynthFuzz vs {fuzzer}": df[df["Fuzzer"] == "SynthFuzz"]["Count"].iloc[0] / df[df["Fuzzer"] == fuzzer]["Count"].iloc[0]
        for fuzzer in fuzzers_to_compare
    }
    print(f"===={subject}=====")
    for compare_name, value in diffs[subject].items():
        print(f"{compare_name}: {value}")

total_diffs = {
    "Grammarinator": 0,
    "MLIRSmith": 0,
    "NeuRI": 0,
    "Seeds Only": 0,
    "Min": 0,
}
for subject,diff in diffs.items():
    if subject == "iree":
        print("skip")
        continue
    min_diff = min(diff.values())
    total_diffs["Min"] += min_diff / 4
    for against in total_diffs.keys():
        if against == "Min":
            continue
        total_diffs[against] += diff[f"SynthFuzz vs {against}"] / 4

print("=====Average Diversity Difference======")
for against, proportion in total_diffs.items():
    print(f"SynthFuzz v. {against}: {proportion}")
