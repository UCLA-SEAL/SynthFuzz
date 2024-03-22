import os
from pathlib import Path
import shutil
import subprocess
import concurrent.futures

import click
from tqdm import tqdm


def process_file(filepath: Path, oracle_tmplt: str, output_dir: Path):
    oracle = oracle_tmplt.replace("%inputpath", str(filepath))
    result = subprocess.run(
        oracle, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if result.returncode == 0:
        output_path = output_dir / filepath.name
        output_path_temp = output_dir / f"{filepath.name}.tmp"
        shutil.copy(filepath, output_path_temp)
        os.rename(output_path_temp, output_path)
        return True
    else:
        return False


@click.command()
@click.argument(
    "input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.argument(
    "output_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--oracle-tmplt", type=str, required=True)
@click.option("--max-workers", type=int, default=int(os.cpu_count() * 3 / 4))
def main(input_dir: Path, output_dir: Path, oracle_tmplt: str, max_workers: int):
    filepaths = list(input_dir.glob("*.mlir"))
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
        copied = 0
        future_to_filepath = {
            executor.submit(process_file, filepath, oracle_tmplt, output_dir): filepath
            for filepath in filepaths
        }
        for future in tqdm(
            concurrent.futures.as_completed(future_to_filepath), total=len(filepaths)
        ):
            try:
                if future.result():
                    copied += 1
            except Exception as e:
                print(f"File {future_to_filepath[future]} failed: {e}")

    print(f"Copied: {copied}/{len(filepaths)}")


if __name__ == "__main__":
    main()
