import os
import time
from argparse import ArgumentParser
import subprocess
from multiprocessing import Pool, Lock
from dataclasses import dataclass

import pandas as pd

# Global lock for CSV file writing
csv_lock = Lock()


def execute_file(command_prefix_template, file_path, output_file, timeout=30):
    # Prepare command
    command = [
        arg.replace("%inputpath", file_path).replace("%inputname", os.path.basename(file_path)) for arg in command_prefix_template
    ]

    # Start the process
    start_time = time.time()
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for process to finish and get the return code
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return_code = proc.returncode
        elapsed_time = time.time() - start_time
        # Print the command executed, return code, stdout, and stderr to a CSV file
        with csv_lock:
            with open(output_file, "a") as f:
                f.write(
                    f"{file_path}\t{return_code}\t{elapsed_time}\t{stdout}\t{stderr}\n"
                )
    except subprocess.TimeoutExpired:
        # Timeout reached. Terminate process.
        proc.terminate()
        return_code = -9991
        stdout, stderr = "N/A", "Timed out."

        # Log this in the CSV file
        with csv_lock:
            with open(output_file, "a") as f:
                f.write(f"{file_path}\t{return_code}\t{timeout}\t{stdout}\t{stderr}\n")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("input_dir")
    parser.add_argument("output_file")
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument(
        "--command-prefix",
    )
    parser.add_argument("--max-threads", default=8, type=int)
    args = parser.parse_args()

    if not args.overwrite and os.path.exists(args.output_file):
        # exclude already evaluted files
        df = pd.read_csv(args.output_file, sep="\t")
        done_filenames = set(df["filename"])
    else:
        # Initialize CSV
        with open(args.output_file, "w") as f:
            f.write(
                "\t".join(
                    ["filename", "return_code", "elapsed_time", "stdout", "stderr"]
                )
                + "\n"
            )
        done_filenames = set()

    # Get all files in the directory
    file_paths = [
        entry.path
        for entry in os.scandir(args.input_dir)
        if os.path.isfile(entry.path)
        and entry.name.endswith(".mlir")
        and entry.path not in done_filenames
    ]
    file_paths.sort()

    # split command prefix
    command_prefix = args.command_prefix.split(" ")

    # Create a pool of workers
    # Each worker will run the `execute_file` function for each file
    with Pool(processes=args.max_threads) as pool:
        pool.starmap(
            execute_file,
            zip(
                [command_prefix] * len(file_paths),
                file_paths,
                [args.output_file] * len(file_paths),
            ),
        )
