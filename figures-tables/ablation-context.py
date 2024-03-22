import pandas as pd
import json
from pathlib import Path
from mlirmut.scripts.compute_pairs import reduce_to_dialect
import yaml
import os

def load_final_cov(path):
    nums = [int(p.stem.split(".")[0]) for p in path.glob("*.profdata.json")]
    max_cov_file_num = max(nums)
    final_path = path / f"{max_cov_file_num}.profdata.json"
    with final_path.open("r") as f:
        return json.load(f)["data"][0]["totals"]["branches"]["covered"]

def compute_unique_pairs(deps):
    pairs = set()
    for name1, name2s in deps.items():
        for name2 in name2s:
            if name1 == name2:
                continue
            pairs.add(frozenset((name1, name2)))
    return pairs
def load_diversity_go(path: Path):
    with path.open("r") as f:
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
def filter_name(name: str):
    if "." not in name:
        return False
    dialect_name = name.split(".")[0]
    if dialect_name not in dialect_names:
        return False
    return True
def filter_op_pairs(pairs: set):
    new_pairs = set()
    for pair in pairs:
        name1, name2 = pair
        if filter_name(name1) and filter_name(name2):
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
def filter_all(full_pairs):
    op_control_pairs = filter_op_pairs(full_pairs["op"]["control"])
    op_data_pairs = filter_op_pairs(full_pairs["op"]["data"])
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

def load_stderr(log_dir):
    all_stderr = dict()
    for stderr_file in log_dir.glob("batch_stderr*"):
        with open(stderr_file, "r") as f:
            data = json.load(f)
        all_stderr |= data
    return all_stderr
def compute_validity(stderrs):
    total = 0
    num_valid = 0
    for stderr in stderrs.values():
        total += 1
        if len(stderr) == 0:
            num_valid += 1
    return num_valid

cache_path = "/synthfuzz/data/ablation/context.parquet"
if os.path.exists(cache_path):
    tarr = pd.read_parquet(cache_path)
else:
    tarr = pd.DataFrame(
        [
            {"k": 0, "l": 0, "r": 0},
            {"k": 0, "l": 2, "r": 2},
            {"k": 0, "l": 4, "r": 4},
            {"k": 2, "l": 0, "r": 2},
            {"k": 2, "l": 2, "r": 4},
            {"k": 2, "l": 4, "r": 0},
            {"k": 4, "l": 0, "r": 4},
            {"k": 4, "l": 2, "r": 0},
            {"k": 4, "l": 4, "r": 2},
        ]
    )
    exp_fmt = "k{k}-l{l}-r{r}"
    parent_dir = Path("/workdir/mlir-eval/mlir-ablation/context/")

    # Coverage
    coverages = []
    def load_final_cov(path):
        nums = [int(p.stem.split(".")[0]) for p in path.glob("*.profdata.json")]
        max_cov_file_num = max(nums)
        final_path = path / f"{max_cov_file_num}.profdata.json"
        with final_path.open("r") as f:
            return json.load(f)["data"][0]["totals"]["branches"]["covered"]
    for _, row in tarr.iterrows():
        k, l, r = row.k, row.l, row.r
        cov = load_final_cov(parent_dir / exp_fmt.format(k=k, l=l, r=r) / "cov-summary")
        coverages.append(cov)
    tarr["cov"] = coverages

    # Diversity
    with open("/synthfuzz/figures-tables/dialect_names/mlir.yml") as f:
        dialect_names = yaml.safe_load(f)
    total_pairs = []
    for _, row in tarr.iterrows():
        k, l, r = row.k, row.l, row.r
        path = parent_dir / exp_fmt.format(k=k, l=l, r=r) / "diversity.go.json"
        diversity = load_diversity_go(path)
        diversity = filter_all(diversity)
        total_pairs.append(len(diversity["dialect"]["control"] | diversity["dialect"]["data"]))
    tarr["div"] = total_pairs

    # Validity
    total_valid = []
    for _, row in tarr.iterrows():
        k, l, r = row.k, row.l, row.r
        log_dir = parent_dir / exp_fmt.format(k=k, l=l, r=r) / "eval-log"
        stderrs = load_stderr(log_dir)
        total_valid.append(compute_validity(stderrs))
    tarr["valid"] = total_valid

    tarr.to_parquet(cache_path)

print("====Experiment Results====")
print(tarr)

# Create a response table
cov_response = pd.DataFrame(
    {
    "level": [0, 2, 4],
    "k": list(tarr.groupby("k").sum()["cov"]/3),
    "l": list(tarr.groupby("l").sum()["cov"]/3),
    "r": list(tarr.groupby("r").sum()["cov"]/3),
    }
)
print("====Coverage Response====")
print(cov_response)

# Create a response table
div_response = pd.DataFrame(
    {
    "level": [0, 2, 4],
    "k": list(tarr.groupby("k").sum()["div"]/3),
    "l": list(tarr.groupby("l").sum()["div"]/3),
    "r": list(tarr.groupby("r").sum()["div"]/3),
    }
)
print("====Diversity Response====")
print(div_response)

# compute response table
valid_response = pd.DataFrame(
    {
    "level": [0, 2, 4],
    "k": list(tarr.groupby("k").sum()["valid"]/3),
    "l": list(tarr.groupby("l").sum()["valid"]/3),
    "r": list(tarr.groupby("r").sum()["valid"]/3),
    }
)
print("====Validity Response====")
print(valid_response)

