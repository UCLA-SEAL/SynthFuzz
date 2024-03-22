from pathlib import Path
from itertools import batched
import click
from tqdm import tqdm

@click.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("output_dir", type=click.Path(path_type=Path))
@click.option("--batch-size", type=int, default=100)
def main(input_dir: Path, output_dir: Path, batch_size: int):
    output_dir.mkdir(parents=True, exist_ok=True)

    input_files = list(input_dir.glob("*.mlir"))
    num_batches = round(len(input_files) / batch_size + 0.5)
    for batch_idx, batch in enumerate(tqdm(batched(input_dir.glob("*.mlir"), batch_size), total=num_batches)):
        with (output_dir / f"batch_{batch_idx}.mlir").open("w") as outf:
            for file_idx, file_path in enumerate(batch):
                if file_idx > 0:
                    outf.write("\n// -----\n")
                with file_path.open("r") as inf:
                    outf.write(inf.read())

if __name__ == "__main__":
    main()