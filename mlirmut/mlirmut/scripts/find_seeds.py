import multiprocessing
import subprocess
from pathlib import Path
import os
import shutil
import click
import logging
import re
import json
from tqdm import tqdm

logger = logging.getLogger(__name__)


@click.command()
@click.argument(
    "repo_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("/workdir/llvm-project"),
)
@click.argument(
    "workdir",
    type=click.Path(exists=False, file_okay=False, path_type=Path),
    default=Path("/workdir/mlir-seeds"),
)
@click.option(
    "--exclude-path",
    type=click.Path(exists=True, path_type=Path),
    multiple=True,
    default=[],
)
@click.option(
    "--mlir-opt-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("/workdir/llvm-project/build/bin/mlir-opt"),
)
@click.option(
    "--grammar",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("/synthfuzz/eval/mlir-hlo/mlir_2023.g4"),
)
@click.option("--start-rule", type=str, default="start_rule")
@click.option("--clean/--no-clean", default=True)
@click.option("--log-level", default="INFO", help="Set the log level.")
def main(
    repo_dir: Path,
    workdir: Path,
    exclude_path: tuple[Path],
    mlir_opt_path: Path,
    grammar: Path,
    start_rule: str,
    clean: bool,
    log_level: str,
):
    # Set up logging
    logger.setLevel(getattr(logging, log_level))
    logger.addHandler(logging.StreamHandler())

    # Set up directories
    original_files_dir = workdir / "original_files"
    split_files_dir = workdir / "split_files"
    generic_dir = workdir / "generic"
    tree_dir = workdir / "trees"
    seeds_dir = workdir / "seeds"
    dirs = [original_files_dir, split_files_dir, seeds_dir, generic_dir, tree_dir]
    logger.info("Setting up directories...")
    for dirpath in tqdm(dirs):
        if clean and dirpath.exists():
            logger.info(f"Cleaning {dirpath}...")
            # delete all visible files/dirs
            for path in dirpath.glob("*"):
                if path.is_file():
                    os.remove(path)
                else:
                    shutil.rmtree(path)
        dirpath.mkdir(parents=True, exist_ok=True)

    # Process files
    find_and_copy_files(repo_dir, original_files_dir, exclude_path)

    command_mapping = split_files(original_files_dir, split_files_dir)
    with open(workdir / "command_mapping.json", "w") as f:
        json.dump(command_mapping, f)

    convert_to_generic(split_files_dir, generic_dir, mlir_opt_path)

    filter_parsable(
        input_dir=generic_dir,
        output_dir=seeds_dir,
        tree_dir=tree_dir,
        grammar=grammar,
        start_rule=start_rule,
    )


def find_and_copy_files(repo_dir: Path, save_dir: Path, exclude_path: tuple[Path]):
    # recursively copy all .mlir files from repo_dir to save_dir
    logger.info("Searching for and copying `.mlir` files...")
    for file in tqdm(repo_dir.rglob("*.mlir")):
        # check if the file belongs to one of the excluded directories:
        if any(file.is_relative_to(path) for path in exclude_path):
            continue
        dst_path = save_dir / file.name
        i = 1
        while dst_path.exists():
            dst_path = dst_path.with_name(file.stem + f"-{i}" + file.suffix)
            i += 1
        # We replace all `.` in the middle since grammarinator cuts it off
        dst_path = dst_path.with_name(dst_path.stem.replace(".", "-") + dst_path.suffix)
        shutil.copy(file, dst_path)
    logger.info("Finished copying files.")


def split_files(in_dir: Path, out_dir: Path):
    logger.info("Splitting files...")
    command_mapping: dict[str, list[str]] = dict()
    files = list(in_dir.glob("*.mlir"))
    for file in tqdm(files):
        cases = []
        with file.open("r") as f:
            case = ""
            for line in f:
                if line.startswith("// RUN:"):
                    if file.name not in command_mapping:
                        command_mapping[file.name] = []
                    command_mapping[file.name].append(line)
                elif line.startswith("// -----"):
                    cases.append(case)
                    case = ""
                elif line.strip().startswith("//"):
                    continue
                else:
                    case += line
            if len(case.strip()) > 0:
                cases.append(case)
        for i, case in enumerate(cases):
            if len(case.strip()) == 0:
                continue
            out_filepath = out_dir / (file.stem + f"-{i}" + file.suffix)
            with out_filepath.open("w") as f:
                f.write(case)
    logger.info("Finished splitting files.")
    return command_mapping


def convert_to_generic(input_dir: Path, output_dir: Path, mlir_opt_path: Path):
    logger.info("Converting to generic form...")
    inputs = list(input_dir.glob("*"))
    with multiprocessing.Pool() as pool:
        list(
            tqdm(
                pool.imap(
                    convert_single_file,
                    [
                        (input_path, output_dir / input_path.name, mlir_opt_path)
                        for input_path in inputs
                    ],
                ),
                total=len(inputs),
            )
        )
    logger.info("Finished converting to generic form.")


def convert_single_file(args):
    input_path, output_path, mlir_opt_path = args
    subprocess.run(
        f"{mlir_opt_path} --allow-unregistered-dialect --mlir-print-op-generic {input_path}> {output_path}",
        shell=True,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    with output_path.open("r") as f:
        if f.read().strip() == "":
            os.remove(output_path)


def filter_parsable(
    input_dir: Path,
    output_dir: Path,
    tree_dir: Path,
    grammar: Path,
    start_rule: str,
):
    logger.info("Parsing files...")
    subprocess.run(
        f"grammarinator-parse {grammar} -i {input_dir}/* -o {tree_dir} -r {start_rule}",
        shell=True,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    logger.info("Filtering parsable files...")
    for tree_file in tree_dir.glob("*"):
        input_name = tree_file.stem.split(".")[0] + ".mlir"
        input_path = input_dir / input_name
        output_path = output_dir / input_name
        shutil.copy(input_path, output_path)
    logger.info("Finished filtering parsable files.")


if __name__ == "__main__":
    main()
