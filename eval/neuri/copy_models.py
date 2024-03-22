import shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import os
import sys
import click

# Hard-coded input and output directories
input_dir = Path("/workdir/neuri-models/tensorflow-neuri-n5.models")
output_dir = Path("/workdir/mlir-eval/neuri/tf-models")

def copy_model(model_name):
    """Copy a single TensorFlow saved_model directory from input to output."""
    src = input_dir / model_name / "model" / "tfnet"
    dst = output_dir / model_name
    shutil.copytree(str(src), str(dst))

def print_progress(completed, total):
    sys.stdout.write('\r[{0}/{1}] Copying...'.format(completed, total))
    sys.stdout.flush()

@click.command()
@click.option('--workers', '-w', type=int, default=os.cpu_count(), help='Number of worker processes')
def main(workers):
    # Get a list of all directories in the input directory
    model_dirs = [d.name for d in input_dir.iterdir() if d.is_dir()]
    total = len(model_dirs)

    # Create the output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use a ProcessPoolExecutor to copy the directories in parallel
    with ProcessPoolExecutor(max_workers=workers) as executor:
        # Submit tasks to copy each directory
        futures = [executor.submit(copy_model, model_dir) for model_dir in model_dirs]

        # Wait for all tasks to complete and print progress
        completed = 0
        for future in futures:
            future.result()
            completed += 1
            print_progress(completed, total)

    print_progress(total, total)
    print("\nCopying completed successfully.")

if __name__ == "__main__":
    main()