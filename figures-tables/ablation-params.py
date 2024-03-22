import os
import json
from pathlib import Path
import re
import pandas as pd

def load_stderr(log_dir):
    all_stderr = dict()
    for stderr_file in log_dir.glob("batch_stderr*"):
        with open(stderr_file, "r") as f:
            data = json.load(f)
        all_stderr |= data
    return all_stderr

error_types = {
    # def-use/redef
    "undefined": re.compile(
        r"use of undeclared SSA"
        r"|undefined symbol"
        r"|does not reference a valid"
        r"|value defined outside region"
        r"|op callee function .+ not found in nearest symbol table\n"
        r"|reference to invalid result"
    ),
    "redefinition": re.compile(r"redefinition"),

    # structural
    "invalid parent": re.compile(
        r"expects parent"
        r"|op must appear in a (function|module)-like op"
    ),
    "cardinality": re.compile(
        r"operation should have no operands and no results"
        r"|expected \d+ operand|op requires (a single|zero) operand|incorrect number of operands"
        r"|op requires (one|zero) result|operation defines \d+ results but was provided"
        r"|op has \d+ operands, but enclosing function|op returns \d+ value but enclosing function"
    ),
    "wrong structure": re.compile(r"op requires (one|zero) region"),
    "invalid terminator": re.compile(
        r"op must be the last operation"
        r"|block with no terminator"
        r"|region to terminate"
    ),
    "does not dominate": re.compile(r"operand #\d+ does not dominate this use"),
    "other structure": re.compile(r"op region .+ failed to verify constraint"),

    # attribute/property
    "invalid atrributes/properties": re.compile(
        r"invalid properties"
        r"|op requires attribute"
        r"|expected attribute"
        r"|to close properties"
        r"|error: missing .+ attribute\n"
        r"|duplicate key"
        r"|unknown attribute"
        r"|unknown SPIR-V attribute"
        r"|op missing SPIR-V target env attribute"
        r"|expects the parent symbol table to have"
    ),
    "cannot be public": re.compile(r"op symbol declaration cannot have public visibility\n"),
    "visibility": re.compile(r"op visibility expected to be one of"),
    "fast math flags": re.compile(r"FastMathFlags to be one of"),

    # Type errors
    "invalid type": re.compile(
        r"expected integer"
        r"|must have static shape"
        r"|error: definition of SSA value .+ has type"
        r"|expected SSA operand"
        r"|op expected reassociation map"
        r"|op operand #\d+ must be"
        r"|failed to satisfy constraint: .+ (attribute\n|type\n)"
        r"|attribute not of type"
        r"|must be tensor of complex type"
        r"|expected floating-point elements"
        r"|op result #\d+ must be"
        r"|integer constant out of range"
        r"|op requires the same type"
        r"|op unsupported type"
        r"|expected .+ type"
        r"|expected upper bounds map"
        r"|op only .+ condition values are supported"
    ),
    "conflicting type": re.compile(r"expects different type|expected function type|op type of entry block|type of return operand|op failed to verify that all of"),
    "function signature": re.compile(r"op entry block must have"),
    "shape inference": re.compile(r"inferred shape of"),

    # syntax error
    "syntax": re.compile(
        r"expected '.*'"
        r"|expected operation name in quotes"
        r"|unbalanced .+ character"
    ),

    # Other??
    "name op no results": re.compile(r"cannot name an operation with no results"),
    "assertion": re.compile(r"Assertion"),

    # Invalid compiler pass options
    "unregistered": re.compile(r"unregistered (dialect|operation)"),
    "no such option": re.compile(r"no such option"),
    "unknown option": re.compile(r"Unknown command line argument"),
    "failed to legalize": re.compile(r"failed to legalize"),
}
def categorize_error(stderr):
    cat_errs = {"other": [], "valid": []}
    for error_type, pattern in error_types.items():
        cat_errs[error_type] = []
    for stderrstr in stderr.values():
        categorized = False
        for error_type, pattern in error_types.items():
            if pattern.search(stderrstr):
                cat_errs[error_type].append(stderrstr)
                categorized = True
        if stderrstr == '':
            cat_errs["valid"].append(stderrstr)
        elif not categorized:
            cat_errs["other"].append(stderrstr)
    return cat_errs

def broad_category(errs):
    broad_categories = {
        "valid": ["valid"],
        "general mlir": ["undefined", "redefinition", "conflicting type"],
        # these are errors we exclude either because they do not relate to input validty checks or otherwise
        "exclude errors": ["unregistered", "no such option", "unknown option", "failed to legalize", "name op no results", "syntax"],
        "op specific type errors": ["invalid type", "function signature", "shape inference", "assertion"],
        "structural": ["invalid parent", "cardinality", "wrong structure", "invalid terminator", "does not dominate", "other structure"],
    }

    broad_errs = {"op specific": []}
    for bcat, includes in broad_categories.items():
        broad_errs[bcat] = []

    for error_type, errstrs in errs.items():
        categorized = False
        for bcat, includes in broad_categories.items():
            if error_type in includes:
                broad_errs[bcat].extend(errstrs)
                categorized = True
        if not categorized:
            broad_errs["op specific"].extend(errstrs)
    return broad_errs

cache_path = "/synthfuzz/data/ablation/with-param-log"
if os.path.exists(cache_path):
    pstderr = load_stderr(Path(cache_path))
else:
    pstderr = load_stderr(Path("/workdir/mlir-eval/mlir-ablation/with-parameters/eval-log"))
cache_path = "/synthfuzz/data/ablation/no-param-log"
if os.path.exists(cache_path):
    npstderr = load_stderr(Path(cache_path))
else:
    npstderr = load_stderr(Path("/workdir/mlir-eval/mlir-ablation/no-parameters/eval-log"))
pbroad_errs = broad_category(categorize_error(pstderr))
for bcat, errs in pbroad_errs.items():
    print(f"{bcat}: {len(errs)}")
print("==========")
npbroad_errs = broad_category(categorize_error(npstderr))
for bcat, errs in npbroad_errs.items():
    print(f"{bcat}: {len(errs)}")

def format_df(broad_errs, name):
    idx = pd.MultiIndex.from_tuples(
        [
            (name, "Valid", "Valid"),
            (name, "Invalid", "Dialect Specific"),
            (name, "Invalid", "General MLIR"),
            (name, "Invalid", "Invalid Options"),
        ]
    )
    df = pd.DataFrame(
        {
            "Count": [
                len(broad_errs["valid"]),
                len(broad_errs["op specific"])
                + len(broad_errs["op specific type errors"])
                + len(broad_errs["structural"]),
                len(broad_errs["general mlir"]),
                len(broad_errs["exclude errors"]),
            ]
        },
        index=idx,
    )
    fraction = df["Count"] / df["Count"].sum()
    df["Percent"] = fraction.round(3) * 100
    df = df.stack()
    df = df.swaplevel(1,3)
    df = df.unstack().unstack().unstack()
    for col in df.columns:
        if (col[:2] == ("Invalid", "Valid")
            or (col[0] == "Valid" and col[1] != "Valid")):
            df = df.drop(columns=[col])
    return df

pdf = format_df(pbroad_errs, "With Parameters")
npdf = format_df(npbroad_errs, "Without Parameters")
all_df = pd.concat([pdf, npdf])
for col in all_df.columns:
    if col[-1] == "Count":
        all_df[col] = all_df[col].apply(lambda val: f"{int(val)}")
    else:
        all_df[col] = all_df[col].apply(lambda val: f"{val:.1f}\\%")
print(all_df.T)
