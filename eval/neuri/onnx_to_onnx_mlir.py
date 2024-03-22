import os
from pathlib import Path
from tqdm import tqdm
import shutil
import subprocess
import concurrent.futures

def convert_single_onnx_to_mlir(input_file: Path, output_folder: Path):
    # Get the base name of the input file without the extension
    # onnx-mlir will append .onnx.mlir to the prefix
    output_prefix = input_file.stem
    output_path_prefix = output_folder / output_prefix
    predicted_output = output_path_prefix.with_name(output_prefix + ".onnx.mlir")
    if predicted_output.exists():
        return
    subprocess.run(['/workdir/onnx-mlir/build/Debug/bin/onnx-mlir', '--EmitONNXIR', str(input_file), '-o', str(output_path_prefix)], check=False)

def convert_onnx_to_mlir(input_folder: Path, output_folder: Path):
    # Find all .onnx files in the input folder
    onnx_files = list(input_folder.glob("*.onnx"))

    # Create a ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        # Submit tasks to the executor
        futures = [ executor.submit(convert_single_onnx_to_mlir, input_file, output_folder) for input_file in onnx_files ]

        # Wait for all tasks to complete
        for _ in tqdm(concurrent.futures.as_completed(futures), desc="Converting ONNX to MLIR", unit="file"):
            pass

if __name__ == "__main__":
    input_folder = Path("/workdir/mlir-eval/neuri/onnx-models")
    output_folder = Path("/workdir/mlir-eval/neuri/onnx-mlir")

    # Ensure the output folder exists
    output_folder.mkdir(parents=True, exist_ok=True)

    # Convert ONNX to MLIR
    convert_onnx_to_mlir(input_folder, output_folder)

    # Remove all .tmp files in the output folder
    for tmp_file in tqdm(output_folder.glob("*.tmp"), desc="Removing temporary files", unit="file"):
        tmp_file.unlink()