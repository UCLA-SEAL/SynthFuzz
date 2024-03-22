import os
from argparse import ArgumentParser
from pathlib import Path

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    args = parser.parse_args()

    path_mappings: dict[Path, Path] = dict()
    for entry in os.scandir(args.input_dir):
        entry_path = Path(entry.path)
        file_number = int(entry.name.split(".")[0])
        path_mappings[entry_path] = entry_path.with_name(f"{file_number:05d}{''.join(entry_path.suffixes)}")
    # we don't rename in the first for loop in case there are files that have a numerical name
    for input_path, output_path in path_mappings.items():
        input_path.rename(output_path)