import os
import shutil
import tempfile
from pathlib import Path
import subprocess
import re
from dataclasses import dataclass
import click
import json
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed, ThreadPoolExecutor
import traceback


@dataclass
class DecomposedOp:
    indent_level: int
    return_values: list[str]
    operand_values: list[str]
    full_name: str
    dialect: str

@dataclass
class DeferredOp:
    line_idx: int
    line: str
    op: DecomposedOp


def decompose_op(line: str):
    """Decomposes an operation into its component parts."""
    # Remove leading spaces
    stripped_line = line.lstrip()

    # first check if it's even an operation by looking for either a `%` or a `"`
    if not (stripped_line.startswith("%") or stripped_line.startswith('"')):
        return None

    # Compute the indent level by counting the number of spaces at the beginning of the line and dividing by 2
    indent_level = (len(line) - len(line.lstrip())) // 2

    # Extract any return values
    return_values_substr = stripped_line[: stripped_line.find('"')]
    return_values = re.findall(r"%([^\s,:]+)", return_values_substr)

    # Extract the operation name and dialect
    full_name_match = re.search(r'"(\S+?)"', stripped_line)
    if full_name_match is None:
        raise ValueError(f"Failed to extract operation name from line: {line}")
    full_name = full_name_match.group(1)
    dialect = full_name.split(".")[0]

    # Extract any operands
    operand_substr_match = re.search(r"\((.*?)\)", stripped_line)
    if operand_substr_match is None:
        raise ValueError(f"Failed to extract operands from line: {line}")
    operand_substr = operand_substr_match.group(1)
    operand_values = re.findall(r"%([^\s,:#]+)", operand_substr)

    return DecomposedOp(indent_level, return_values, operand_values, full_name, dialect)


def decompose_block_label(line: str):
    """Decomposes a block label into its component parts."""
    stripped_line = line.lstrip()

    # First check if it's a block label by looking for a `^`
    if not stripped_line.startswith("^"):
        return None

    # Extract any operands
    operand_substr_match = re.search(r"\((.*?)\)", stripped_line)
    if operand_substr_match is None:
        return []  # block label does not have any operands
    operand_substr = operand_substr_match.group(1)
    operand_values = re.findall(r"%([^\s,:#]+)", operand_substr)

    return operand_values


def compute_op_pairs(formatted_mlir: str):
    """Collects all pairs of operations with control dependencies."""
    control_deps: dict[str, set[str]] = dict()
    data_deps: dict[str, set[str]] = dict()
    current_indent = 0
    parent_ops: list[DecomposedOp] = []
    prev_op = None
    value_map: dict[str, tuple[str, int]] = dict()
    deferred_ops: list[DeferredOp] = list()
    for line_idx, line in enumerate(formatted_mlir.split("\n")):
        op = decompose_op(line)
        if op is None:
            # check if it's a block label
            possible_args = decompose_block_label(line)
            if possible_args is None:
                continue  # not a block label
            if prev_op is None:
                raise ValueError(
                    f"Block label without associated operation on line {line_idx}: {line}"
                )
            for arg in possible_args:
                if arg not in value_map:
                    # the value is only visible in the next block (one indent in)
                    value_map[arg] = (prev_op.full_name, prev_op.indent_level + 1)
            continue

        # when we reach a new indent, then we should set the parent
        # operation to the previous operation
        if op.indent_level > current_indent:
            if prev_op is None:
                raise ValueError(
                    f"Indent without associated operation on line {line_idx}: {line}"
                )
            parent_ops.append(prev_op)
            current_indent = op.indent_level
        elif op.indent_level < current_indent:
            # add data dependencies for deferred operations
            for d_op in deferred_ops:
                for operand in d_op.op.operand_values:
                    if operand not in value_map:
                        raise ValueError(
                            f"Failed to find mapping for operand `{operand}` in line {d_op.line_idx}: `{d_op.line}`."
                        )
                    if d_op.op.full_name not in data_deps:
                        data_deps[d_op.op.full_name] = set()
                    data_deps[d_op.op.full_name].add(value_map[operand][0])
            # remove deferred operations that are at a higher indent than we are
            # now since there are no other possible values they can reference
            deferred_ops = [d_op for d_op in deferred_ops if d_op.op.indent_level <= op.indent_level]

            # remove parent ops and values that are no longer visible
            parent_ops.pop()
            # remove values that are no longer visible
            value_map = {
                val_name: (op_name, indent_level)
                for val_name, (op_name, indent_level) in value_map.items()
                if indent_level <= op.indent_level
            }
            current_indent = op.indent_level

        # add control dependencies
        if op.full_name not in control_deps:
            control_deps[op.full_name] = set()
        control_deps[op.full_name] |= {parent_op.full_name for parent_op in parent_ops}

        # add data dependencies
        for operand in op.operand_values:
            if operand not in value_map:
                # the operand may refer to a later operation (graphs with cycles)
                deferred_ops.append(DeferredOp(line_idx=line_idx, line=line, op=op))
                continue
            if op.full_name not in data_deps:
                data_deps[op.full_name] = set()
            data_deps[op.full_name].add(value_map[operand][0])

        # since its SSA, then we can assume there's a many-to-one mapping from return values to operations
        for ret_value in op.return_values:
            if ret_value not in value_map:
                value_map[ret_value] = (op.full_name, op.indent_level)

        prev_op = op


    return control_deps, data_deps


def reduce_to_dialect(op_deps: dict[str, set[str]]):
    dialect_deps: dict[str, set[str]] = dict()
    for name, deps in op_deps.items():
        dialect = name.split(".")[0]
        if dialect not in dialect_deps:
            dialect_deps[dialect] = set()
        dialect_deps[dialect] |= {dep.split(".")[0] for dep in deps}
    return dialect_deps


def format_mlir(text: str, mlir_opt_path: Path):
    """
    Formats MLIR code using the mlir-opt tool.

    Parameters:
    text (str): The MLIR code to format.

    Returns:
    str: The formatted MLIR code.

    Raises:
    subprocess.CalledProcessError: If the mlir-opt tool returns a non-zero exit status.
    """
    try:
        process = subprocess.run(
            [
                str(mlir_opt_path),
                "--mlir-print-op-generic",
                "--allow-unregistered-dialect",
            ],
            input=text,
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(e.stderr)
        raise e
    return process.stdout


def compute_dependencies_file(filepath: Path, mlir_opt_path: Path):
    with filepath.open("r") as f:
        raw_mlir = f.read()
    try:
        formatted_mlir = format_mlir(raw_mlir, mlir_opt_path)
        control_deps, data_deps = compute_op_pairs(formatted_mlir)
    except Exception as e:
        raise Exception(f"Failed to compute dependencies in {filepath}.") from e
    return control_deps, data_deps


def unify_deps(dep1, dep2):
    for k, v in dep2.items():
        if k in dep1:
            dep1[k] |= v
        else:
            dep1[k] = v


def make_serializable(deps: dict):
    new_deps = dict()
    for k, v in deps.items():
        if isinstance(v, set):
            new_deps[k] = list(v)
        else:
            new_deps[k] = v
    return new_deps


@click.command()
@click.argument("mlirpath", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), default=None)
@click.option("--cache-dir", type=click.Path(path_type=Path), default=None)
@click.option("--max-workers", type=int, default=int(os.cpu_count() * 3 / 4))
@click.option("--mlir-opt-path", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=Path("/workdir/llvm-project/build/bin/mlir-opt"))
def main(mlirpath: Path, output: Path | None, cache_dir: Path | None, max_workers: int, mlir_opt_path: Path):
    if mlirpath.is_file():
        all_control_deps, all_data_deps = compute_dependencies_file(mlirpath, mlir_opt_path)
    else:
        if cache_dir is None:
            # create a unique cache directory name
            cache_dir = Path(tempfile.mkdtemp(prefix="compute-pair-cache-"))
        cache_dir.mkdir(parents=True, exist_ok=True)
        all_control_deps = dict()
        all_data_deps = dict()
        seen_files = set()
        # load the cache if any
        max_cache_file = max(
            (int(filepath.stem) for filepath in cache_dir.glob("*.json")), default=None
        )
        if max_cache_file is not None:
            with (cache_dir / f"{max_cache_file}.json").open("r") as f:
                data = json.load(f)
                all_control_deps = {
                    name: set(deps) for name, deps in data["control"].items()
                }
                all_data_deps = {name: set(deps) for name, deps in data["data"].items()}
                seen_files = set(data["files"])

        filepaths = [
            filepath
            for filepath in mlirpath.glob("*.mlir")
            if str(filepath) not in seen_files
        ]
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_filepath = {
                executor.submit(compute_dependencies_file, filepath, mlir_opt_path): filepath
                for filepath in filepaths
            }
            processed_files = set()
            for idx, future in enumerate(
                tqdm(as_completed(future_to_filepath), total=len(filepaths))
            ):
                try:
                    control_deps, data_deps = future.result()
                    unify_deps(all_control_deps, control_deps)
                    unify_deps(all_data_deps, data_deps)
                    processed_files.add(str(future_to_filepath[future]))
                except Exception:
                    print(
                        f"Failed to compute dependencies in {future_to_filepath[future]} because of:"
                    )
                    traceback.print_exc()
                if idx % 100 == 0:
                    cache_path = cache_dir / f"{idx}.json"
                    print(f"Processed {idx} files saving to {cache_path}")
                    with cache_path.open("w") as f:
                        json.dump(
                            {
                                "control": make_serializable(all_control_deps),
                                "data": make_serializable(all_data_deps),
                                "files": list(processed_files),
                            },
                            f,
                        )

    all_deps = {
        "dialect": {
            "control": make_serializable(reduce_to_dialect(all_control_deps)),
            "data": make_serializable(reduce_to_dialect(all_data_deps)),
        },
        "op": {
            "control": make_serializable(all_control_deps),
            "data": make_serializable(all_data_deps),
        },
    }
    if output is None:
        print(json.dumps(all_deps))
    else:
        with output.open("w") as f:
            json.dump(all_deps, f)

    # clean up the cache since we're done
    if cache_dir is not None:
        shutil.rmtree(cache_dir)


if __name__ == "__main__":
    main()
