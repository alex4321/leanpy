from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .errors import ExecutionError


@dataclass(frozen=True)
class RunResult:
    """Result of executing a Lean snippet."""

    file: str
    stdout: str
    stderr: str
    returncode: int


def run_code(project_path: Path, *, imports: List[str], code: str, timeout: int = 30) -> RunResult:
    """
    Run a Lean snippet inside the given project.

    Writes a temp file under `.leanpy/run_<hash>.lean` that contains the provided
    imports followed by the code, then executes `lake env lean <file>`.

    Returns RunResult; raises ExecutionError on non-zero exit or timeout.
    """
    project_path = project_path.expanduser().resolve()
    tmp_dir = project_path / ".leanpy"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha1(
        ("\n".join(imports) + "\n" + code).encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:12]
    file_path = tmp_dir / f"run_{digest}.lean"

    with file_path.open("w", encoding="utf-8") as f:
        for imp in imports:
            f.write(f"import {imp}\n")
        f.write("\n")
        f.write(code.strip())
        f.write("\n")

    try:
        proc = subprocess.run(
            ["lake", "env", "lean", str(file_path)],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExecutionError(f"Lean execution timed out after {timeout}s") from exc

    if proc.returncode != 0:
        raise ExecutionError(
            f"Lean exited with {proc.returncode}.\nstdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )

    return RunResult(
        file=str(file_path),
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
    )

