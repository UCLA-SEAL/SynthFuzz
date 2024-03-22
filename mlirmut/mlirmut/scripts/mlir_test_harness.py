import os
import subprocess
import click
from pathlib import Path
import logging
import random
import json
from itertools import chain, batched
from typing import Iterable
import concurrent.futures
from tqdm import tqdm
import time

logger = logging.getLogger(__name__)


@click.command()
@click.argument(
    "input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.argument("log_dir", type=click.Path(path_type=Path))
@click.argument(
    "target_binary", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option("--log-level", default="INFO", help="Set the log level.")
@click.option("--seed", default=None, type=int)
@click.option(
    "--association-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("/workdir/mlir-dialect-associations.json"),
)
@click.option("--max-options", default=5, type=int)
@click.option("--random-mode/--no-random-mode", default=False)
@click.option(
    "--temp-dir",
    type=click.Path(path_type=Path),
    default=Path("/tmp/mlir-test-harness"),
)
@click.option(
    "--cov-batch-dir",
    type=click.Path(path_type=Path),
    default=Path("/tmp/mlir-test-harness/batch"),
)
@click.option("--cumulative-cov-path", type=click.Path(path_type=Path), default=None)
@click.option("--max-threads", default=int(os.cpu_count() * 1 / 8), type=int)  # type: ignore
@click.option("--batch-size", default=20, type=int)
@click.option("--timing-only/--no-timing-only", default=False)
@click.option("--resume/--no-resume", default=False)
@click.option("--find-crashes/--no-find-crashes", default=False)
@click.option("--save-stderr/--no-save-stderr", default=False)
def main(
    input_dir: Path,
    cumulative_cov_path: Path,
    log_dir: Path,
    target_binary: Path,
    log_level: str,
    seed: int,
    association_file: Path,
    max_options: int,
    random_mode: bool,
    temp_dir: Path,
    batch_size: int,
    cov_batch_dir: Path,
    max_threads: int,
    timing_only: bool,
    resume: bool,
    find_crashes: bool,
    save_stderr: bool,
):
    logger.setLevel(getattr(logging, log_level))
    logger.addHandler(logging.StreamHandler())

    rand = random.Random(seed)

    with association_file.open("r") as f:
        dialect_associations = json.load(f)
    tester = Tester(
        dialect_assocations=dialect_associations,
        rand=rand,
        max_options=max_options,
        log_dir=log_dir,
        random_mode=random_mode,
        target_binary=target_binary,
        temp_dir=temp_dir,
        cov_batch_dir=cov_batch_dir,
        batch_size=batch_size,
        save_stderr=save_stderr,
    )

    batch_mapping = dict()
    input_files = list(input_dir.glob("*.mlir"))
    n_batches = round(len(input_files) / batch_size + 0.5)
    profiles = []

    if timing_only:
        time_execution(input_files, tester, log_dir)
        return
    
    batches: Iterable
    if resume:
        existing_batches = [int(file.stem.split("_")[1]) for file in cov_batch_dir.glob("*.profdata")]
        for last_batch_idx in range(n_batches):
            if last_batch_idx not in existing_batches:
                break
        batches = list(batched(input_files, batch_size))[last_batch_idx:]
    else:
        batches = batched(input_files, batch_size)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_threads) as executor:
        future_to_batch = {
            executor.submit(tester.process_batch, batch, i, False, find_crashes): (i, batch)
            for i, batch in enumerate(batches)
        }
        for future in tqdm(
            concurrent.futures.as_completed(future_to_batch),
            total=len(future_to_batch),
            desc="Batch",
        ):
            i, batch = future_to_batch[future]
            batch_mapping[i] = [str(file) for file in batch]
            if find_crashes:
                continue
            profdata_path = future.result()
            profiles.append(str(profdata_path))
    # log batch_references
    with open(log_dir / "batch_mapping.log.json", "w") as f:
        json.dump(batch_mapping, f)

    # merge all batches
    if cumulative_cov_path and not find_crashes:
        merge_profiles(profiles, cumulative_cov_path)


def merge_profiles(profraw_paths, profdata_path):
    subprocess.run(
        [
            "llvm-profdata",
            "merge",
            "-sparse",
            *profraw_paths,
            "-o",
            profdata_path,
        ],
        check=True,
    )

class DummyPBar:
    def __enter__(self):
        pass
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class Tester:
    def __init__(
        self,
        dialect_assocations: dict[str, list[str]],
        rand: random.Random,
        max_options: int,
        temp_dir: Path,
        log_dir: Path,
        random_mode: bool,
        target_binary: Path,
        cov_batch_dir: Path,
        batch_size: int,
        save_stderr: bool,
    ):
        self.associations = dialect_assocations
        self.rand = rand
        self.max_options = max_options
        self.log_dir = log_dir
        self.temp_dir = temp_dir
        self.random_mode = random_mode
        self.target_binary = target_binary
        self.cov_batch_dir = cov_batch_dir
        self.batch_size = batch_size
        self.save_stderr = save_stderr

    def determine_options(self, mlir_text: str) -> list[str]:
        avail_dialects = [
            dialect for dialect in self.associations if dialect in mlir_text
        ]
        avail_options = []
        for dialect in avail_dialects:
            avail_options.extend(self.associations[dialect])
        return self.rand.sample(
            avail_options, min(len(avail_options), self.max_options)
        )

    def random_options(self):
        avail_options = []
        for option_set in self.associations.values():
            avail_options.extend(option_set)
        return self.rand.sample(
            avail_options, min(len(self.associations), self.max_options)
        )

    def exec_sequential(self, inputs: list[Path], time_each=False):
        cmds = dict()
        for file_path in tqdm(inputs):
            with open(file_path, "r") as f:
                mlir_text = f.read()

            if self.random_mode:
                options = self.random_options()
            else:
                options = self.determine_options(mlir_text)

            cmd = [
                str(self.target_binary),
                *options,
                "-split-input-file",
                str(file_path),
            ]
            cmds[str(file_path)] = cmd
            subprocess.run(
                cmd,
                env={
                    "LLVM_PROFILE_FILE": "/dev/null",
                },
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return cmds

    def eval_batch(self, batch: Iterable[Path], pbar: tqdm | None, crash_only: bool):
        profile_files = []
        cmds = dict()
        crashes = dict()
        stderrs = dict()
        for file_path in batch:
            with open(file_path, "r") as f:
                mlir_text = f.read()
            if self.random_mode:
                options = self.random_options()
            else:
                options = self.determine_options(mlir_text)

            cmd = [
                str(self.target_binary),
                *options,
                "-split-input-file",
                str(file_path),
            ]
            cmds[str(file_path)] = cmd
            profraw_path = self.temp_dir / file_path.with_suffix(".profraw").name
            if crash_only:
                profraw_path = "/dev/null"  # type: ignore
            try:
                proc = subprocess.run(
                    cmd,
                    env={
                        "LLVM_PROFILE_FILE": str(profraw_path),
                    },
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE if self.save_stderr else subprocess.DEVNULL,
                    timeout=30,
                )
            except subprocess.TimeoutExpired:
                crashes[str(file_path)] = {"cmd": cmd, "retcode": -9999}
                continue
            if self.save_stderr:
                stderrs[str(file_path)] = proc.stderr.decode()
            if proc.returncode != 0:
                crashes[str(file_path)] = {"cmd": cmd, "retcode": proc.returncode}
            profile_files.append(profraw_path)
            if pbar:
                pbar.update()
        return profile_files, cmds, crashes, stderrs

    def process_batch(self, batch: Iterable[Path], batch_idx, show_progress, crash_only):
        if show_progress:
            pbar = tqdm(total=self.batch_size, desc=f"Evaluating batch {batch_idx}", leave=False)
        else:
            pbar = DummyPBar()
        with pbar:
            profile_files, cmds, crashes, stderrs = self.eval_batch(batch, pbar if isinstance(pbar, tqdm) else None, crash_only)
            if isinstance(pbar, tqdm):
                pbar.set_description(f"Logging commands")
            # log commands
            with open(self.log_dir / f"batch_cmds_{batch_idx}.log.json", "w") as f:
                json.dump(cmds, f)

            with open(self.log_dir / f"batch_crashes_{batch_idx}.log.json", "w") as f:
                json.dump(crashes, f)

            # log stderr
            if self.save_stderr:
                with open(self.log_dir / f"batch_stderr_{batch_idx}.log.json", "w") as f:
                    json.dump(stderrs, f)

            if crash_only:
                return
            # merge profraw
            if isinstance(pbar, tqdm):
                pbar.set_description(f"Merging profiles for batch {batch_idx}")
            batch_profdata_path = self.cov_batch_dir / f"batch_{batch_idx}.profdata"
            merge_profiles(profile_files, batch_profdata_path)

            # remove profraw files
            if isinstance(pbar, tqdm):
                pbar.set_description(f"Removing raw profiles for batch {batch_idx}")
            for file_path in profile_files:
                os.remove(file_path)
            return batch_profdata_path



def time_execution(input_files: list[Path], tester: Tester, log_dir: Path):
    start_time = time.time()
    cmds = tester.exec_sequential(input_files)
    end_time = time.time()

    with open(log_dir / "timing.log.json", "w") as f:
        json.dump(
            {
                "start_time": start_time,
                "end_time": end_time,
                "duration": end_time - start_time,
                "commands": cmds,
            },
            f,
        )


if __name__ == "__main__":
    main()
