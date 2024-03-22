import os
import subprocess
from pathlib import Path
import click
from concurrent.futures import ThreadPoolExecutor, as_completed

@click.command()
@click.argument('input_dir', default=Path("/workdir/mlir-eval/neuri/tf-models"), type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path))
@click.argument('output_dir', default=Path("/workdir/mlir-eval/neuri/onnx-models"), type=click.Path(file_okay=False, resolve_path=True, path_type=Path))
@click.option('--workers', '-w', default=os.cpu_count(), type=int, help='Number of workers to run in parallel')
def convert_models(input_dir: Path, output_dir: Path, workers: int) -> None:
    """
    Convert TensorFlow saved models to ONNX format.

    INPUT_DIR is the directory containing the TensorFlow saved models.
    OUTPUT_DIR is the directory where the ONNX files will be saved.
    """
    os.makedirs(output_dir, exist_ok=True)

    saved_models = [p for p in input_dir.glob('*') if p.is_dir()]
    total_models = len(saved_models)
    models_completed = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_conversion, input_path, output_dir): input_path for input_path in saved_models}
        for future in as_completed(futures):
            input_path = futures[future]
            try:
                output_file = future.result()
                models_completed += 1
                print(f"\rConverted {models_completed}/{total_models} - {input_path.name} to {output_file}", end="")
            except Exception as e:
                print(f"\rError converting {input_path.name}: {e}", end="")

    print("\nConversion complete.")

def run_conversion(input_path: Path, output_dir: Path) -> Path:
    output_file = output_dir / f"{input_path.name}.onnx"
    command = [
        "python", "-m", "tf2onnx.convert",
        "--saved-model", str(input_path),
        "--output", str(output_file)
    ]
    subprocess.run(command, check=True)
    return output_file

if __name__ == "__main__":
    convert_models()