import os
import subprocess
import click
from pathlib import Path
import tomllib
import itertools
import logging

logger = logging.getLogger(__name__)


def measure_combined_cov(
    profraw_path: Path,
    profdata_path: Path,
    report_path: Path,
    target_binary: str,
    compiler_cmd: str,
):
    logger.info("Running compiler...")
    env = os.environ.copy()
    env["LLVM_PROFILE_FILE"] = str(profraw_path)
    subprocess.run(compiler_cmd, shell=True, env=env)

    logger.info("Generating profdata...")
    subprocess.run(
        f"llvm-profdata merge -sparse {profraw_path} -o {profdata_path}", shell=True
    )

    logger.info("Generating report...")
    subprocess.run(
        f"llvm-cov export -summary-only -instr-profile={profdata_path} {target_binary} > {report_path}",
        shell=True,
    )


def accumulate_cov(
    profdata_paths: list[str],
    profdata_output_path: Path,
    cumulative_export_path: Path,
    target_binary: str,
):
    logger.info("Merging profdata...")
    subprocess.run(
        f"llvm-profdata merge -sparse {' '.join(profdata_paths)} -o {profdata_output_path}",
        shell=True,
    )

    logger.info("Generating report...")
    subprocess.run(
        f"llvm-cov export -summary-only -instr-profile={profdata_output_path} {target_binary} > {cumulative_export_path}",
        shell=True,
    )


@click.command()
@click.option(
    "--config-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--input-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
)
@click.option("--profdata-dir", type=click.Path(path_type=Path), required=True)
@click.option("--temp-dir", type=click.Path(path_type=Path), required=True)
@click.option("--export-dir", type=click.Path(path_type=Path), required=True)
@click.option("--cumulative-dir", type=click.Path(path_type=Path), required=True)
def batched_coverage(
    config_path: Path,
    input_dir: Path,
    profdata_dir: Path,
    temp_dir: Path,
    export_dir: Path,
    cumulative_dir: Path,
):
    with config_path.open("rb") as f:
        config = tomllib.load(f)

    # Set up logging
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    assert input_dir.exists() and input_dir.is_dir()
    profdata_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    export_dir.mkdir(parents=True, exist_ok=True)
    cumulative_dir.mkdir(parents=True, exist_ok=True)

    file_paths = list(input_dir.glob("*.mlir"))
    file_paths.sort(key=lambda x: x.name)

    profdata_paths = []
    for batch_idx, input_batch in enumerate(
        itertools.batched(file_paths, config["batch_size"])
    ):
        # NOTE: if this is later parallelized, the temporary file names need to
        # be changed to prevent overwriting
        logger.info("Processing batch...")
        logger.info("Concatenating files...")
        combined_file_path = temp_dir / f"combined.mlir"
        with open(combined_file_path, "w") as combined_file:
            for input_file_path in input_batch:
                with open(input_file_path, "r") as input_file:
                    combined_file.write(input_file.read())
                    combined_file.write("\n")

        logger.info("Measuring combined coverage...")
        profraw_path = temp_dir / "combined.profraw"
        profdata_path = profdata_dir / f"{batch_idx:05}.profdata"
        profdata_paths.append(str(profdata_path))
        export_path = export_dir / f"{batch_idx:05}.json"
        target_binary = config["target_binary"]
        compiler_cmd = (
            config["compiler_cmd_template"]
            .replace("%input_path", str(combined_file_path))
            .replace("%target_binary", target_binary)
        )
        measure_combined_cov(
            profraw_path=profraw_path,
            profdata_path=profdata_path,
            report_path=export_path,
            target_binary=target_binary,
            compiler_cmd=compiler_cmd,
        )

        logger.info("Accumulating coverage...")
        cumulative_profdata_path = profdata_dir / f"cumulative_{batch_idx:05}.profdata"
        cumulative_export_path = cumulative_dir / f"{batch_idx:05}.json"
        accumulate_cov(
            profdata_paths=profdata_paths,
            profdata_output_path=cumulative_profdata_path,
            cumulative_export_path=cumulative_export_path,
            target_binary=target_binary,
        )


if __name__ == "__main__":
    batched_coverage()
