import os
from argparse import ArgumentParser
import subprocess

from tqdm import tqdm


def merge_files(file_paths: list[str], output_path: str):
    # Convert to profdata
    try:
        status = subprocess.run(
            [
                "/usr/bin/llvm-profdata",
                "merge",
                "-sparse",
                *file_paths,
                "-o",
                output_path,
            ],
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise Exception(f"llvm-profdata merge timed out with files: {file_paths}")
    if status.returncode != 0:
        raise Exception(f"llvm-profdata merge failed with files: {file_paths}")


def main(args):
    # Create an ordered a list of files to process.
    # Files should be named XXXXX.profdata where X is a digit.
    input_filenames = [
        filename
        for filename in os.listdir(args.profdata_dir)
        if filename.endswith(".profdata")
    ]
    input_filenames.sort()
    input_indicies = range(len(input_filenames))
    if args.unnumbered:
        input_filepaths = [os.path.join(args.profdata_dir, filename) for filename in input_filenames]
    else:
        input_filepaths = [
            os.path.join(args.profdata_dir, f"{i:05d}.mlir.profdata")
            for i in input_indicies
        ]
        assert input_filenames == [path.split("/")[-1] for path in input_filepaths]
    max_items = args.max_items if args.max_items >= 0 else len(input_filepaths)

    # Create an ordered list of output indicies. Each output file will contain
    # the cumulative coverage of input files with an index equal to or less than
    # the output index. For example, the output file 00012.profdata will
    # contain the cumulative coverage of input files 00000.profdata to
    # 00012.profdata.
    output_indicies = [i for i in range(args.interval, max_items, args.interval)]
    max_index = max_items - 1
    if max_index not in output_indicies:
        output_indicies.append(max_index)

    if len(output_indicies) == 0:
        return

    # The first cumulative profdata is the first args.interval files.
    output_index = output_indicies[0]
    output_filepath = os.path.join(args.cumulative_dir, f"{output_index}.profdata")
    if args.overwrite or not os.path.exists(output_filepath):
        merge_files(input_filepaths[: args.interval], output_filepath)
    prev_output_index = output_index
    prev_output_filepath = output_filepath

    # For each subsequent index, we merge the previous cumulative file with the
    # next interval of input files.
    for output_index in tqdm(output_indicies[1:]):
        output_filepath = os.path.join(args.cumulative_dir, f"{output_index}.profdata")
        if args.overwrite or not os.path.exists(output_filepath):
            merge_files(
                [prev_output_filepath]
                + input_filepaths[prev_output_index:output_index],
                output_filepath,
            )
        prev_output_index = output_index
        prev_output_filepath = output_filepath


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("profdata_dir")
    parser.add_argument("cumulative_dir")
    parser.add_argument("--max-items", type=int, default=-1)
    parser.add_argument("--interval", type=int, default=1)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--unnumbered", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.profdata_dir):
        os.makedirs(args.profdata_dir)

    if not os.path.exists(args.cumulative_dir):
        os.makedirs(args.cumulative_dir)

    main(args)
