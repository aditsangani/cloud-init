#!/usr/bin/env python3
"""Format-check inline shell scripts in GitHub workflow and action YAML."""

import difflib
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml


GITHUB_YAML_DIRS = (Path(".github/workflows"), Path(".github/actions"))
SHFMT_FLAGS = (
    "shfmt",
    "--case-indent",
    "--indent=2",
    "--space-redirects",
    "-",
)
GITHUB_EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.DOTALL)


def run_scripts(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "run" and isinstance(child, str) and "\n" in child:
                yield child
            yield from run_scripts(child)
    elif isinstance(value, list):
        for child in value:
            yield from run_scripts(child)


def main() -> int:
    failed = False
    for directory in GITHUB_YAML_DIRS:
        yaml_paths = (*directory.rglob("*.yml"), *directory.rglob("*.yaml"))
        for path in sorted(yaml_paths):
            with path.open(encoding="utf-8") as yaml_file:
                document = yaml.safe_load(yaml_file)
            for index, script in enumerate(run_scripts(document), start=1):
                # GitHub expressions are substituted by Actions, not shell.
                shell_script = GITHUB_EXPRESSION.sub(
                    "GITHUB_EXPRESSION", script
                )
                try:
                    result = subprocess.run(
                        SHFMT_FLAGS,
                        input=shell_script,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                except OSError as error:
                    print(
                        f"{path}: could not run shfmt: {error}",
                        file=sys.stderr,
                    )
                    return 1
                if result.returncode:
                    print(
                        f"{path}: shfmt failed for multiline run script "
                        f"{index}:",
                        file=sys.stderr,
                    )
                    print(result.stdout or result.stderr, file=sys.stderr)
                    failed = True
                    continue
                if result.stdout != shell_script:
                    print(
                        f"{path}: multiline run script {index} is not "
                        "formatted with shfmt:",
                        file=sys.stderr,
                    )
                    diff = difflib.unified_diff(
                        shell_script.splitlines(keepends=True),
                        result.stdout.splitlines(keepends=True),
                        fromfile="current",
                        tofile="shfmt",
                    )
                    print("".join(diff), file=sys.stderr)
                    failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
