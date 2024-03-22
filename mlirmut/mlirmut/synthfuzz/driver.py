import tomllib
import random
import subprocess
import json
import re


class Driver:
    def __init__(
        self,
        config_path: str,
    ):
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        with open(config["dialect_associations"], "r") as f:
            self.associations = json.load(f)
        self.rand = random.Random(config["seed"])
        self.max_options = config["max_options"]
        self.random_mode = config["use_random_options"]
        self.target_binary = config["target_binary"]
        self.error_filter = re.compile("|".join(config["error_filter_patterns"]))
        self.retcode_filter = config["retcode_filter"]

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

    def test_one(self, mlir_text: str) -> tuple[bool, int, str]:
        if self.random_mode:
            options = self.random_options()
        else:
            options = self.determine_options(mlir_text)
        cmd = [
            str(self.target_binary),
            *options,
            "-split-input-file",
        ]
        proc = subprocess.run(
            cmd,
            input=mlir_text,
            encoding="utf-8",
            env={"LLVM_PROFILE_FILE": "/dev/null"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return (
            # for now we'll just filter by return code
            proc.returncode not in self.retcode_filter, #or self.error_filter.search(proc.stderr) is None,
            proc.returncode,
            proc.stderr,
        )
