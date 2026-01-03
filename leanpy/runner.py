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

    file_path = _run_file_path(tmp_dir, imports, code)
    _write_run_file(file_path, imports, code)

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


def _run_file_path(tmp_dir: Path, imports: List[str], code: str) -> Path:
    """Return the deterministic temp file path for a run."""
    digest = _content_digest(imports, code)
    return tmp_dir / f"run_{digest}.lean"


def _write_run_file(file_path: Path, imports: List[str], code: str) -> None:
    """Write the temp Lean file with imports followed by code."""
    with file_path.open("w", encoding="utf-8") as f:
        for imp in imports:
            f.write(f"import {imp}\n")
        f.write("\n")
        f.write(code.strip())
        f.write("\n")


def _content_digest(imports: List[str], code: str) -> str:
    """Return a short hash of the imports+code content."""
    return (
        hashlib.sha1(
            ("\n".join(imports) + "\n" + code).encode("utf-8"), usedforsecurity=False
        ).hexdigest()[:12]
    )

