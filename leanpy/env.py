from __future__ import annotations

import shutil
import subprocess
from subprocess import CompletedProcess
from typing import Optional

from .errors import LakeNotFound, LeanNotFound, LeanPyError


def _run_command(args: list[str], *, timeout: Optional[int] = 10) -> CompletedProcess[str]:
    """Run a command and capture output without raising on non-zero exit."""
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise LeanPyError(f"Command not found: {args[0]}") from exc


def ensure_lean_installed() -> str:
    """Return the `lean` path or raise LeanNotFound if missing."""
    path = shutil.which("lean")
    if not path:
        raise LeanNotFound(
            "lean binary not found on PATH. Install Lean or activate your toolchain."
        )
    return path


def ensure_lake_installed() -> str:
    """Return the `lake` path or raise LakeNotFound if missing."""
    path = shutil.which("lake")
    if not path:
        raise LakeNotFound(
            "lake binary not found on PATH. Install Lake (Lean 4) or activate your toolchain."
        )
    return path


def lean_version() -> str:
    """Return the detected Lean version string."""
    ensure_lean_installed()
    proc = _run_command(["lean", "--version"])
    return proc.stdout.strip() or proc.stderr.strip()


def lake_version() -> str:
    """Return the detected Lake version string."""
    ensure_lake_installed()
    proc = _run_command(["lake", "--version"])
    return proc.stdout.strip() or proc.stderr.strip()


def lake_supports_add() -> bool:
    """Return True if `lake add` is supported (Lean >= 4.5+ toolchains)."""
    ensure_lake_installed()
    proc = _run_command(["lake", "add", "--help"])
    return proc.returncode == 0

