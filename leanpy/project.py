from __future__ import annotations

import os
import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from typing import List, Optional

from .deps import LeanDependencyConfig, install_dependency
from .env import ensure_lake_installed, ensure_lean_installed, lake_version, lean_version
from .errors import ProjectInitError
from .runner import RunResult, run_code


class LeanProject:
    """
    Manage a Lean/Lake project rooted at `project_path`.

    - If the directory does not exist, create parents and run `lake new <name>` in
      the parent directory.
    - If the directory exists and is empty, run `lake init` inside it.
    - If the directory exists and contains Lake files, reuse it.
    - If the directory exists and is non-empty without Lake files, raise ProjectInitError.
    """

    def __init__(self, project_path: os.PathLike | str, name: Optional[str] = None):
        self.path = Path(project_path).expanduser().resolve()
        ensure_lean_installed()
        ensure_lake_installed()
        self.name = name or self.path.name
        self.dependencies: list[LeanDependencyConfig] = []
        self._init_or_reuse()

    @property
    def lakefile(self) -> Path:
        return self.path / "lakefile.lean"

    def install_dependency(self, dep: LeanDependencyConfig) -> None:
        """Install a dependency via Lake and record it locally."""
        install_dependency(self.path, dep)
        self.dependencies.append(dep)

    def run(self, *, imports: List[str], code: str, timeout: int = 30) -> RunResult:
        """Run Lean code with optional imports inside this project."""
        return run_code(self.path, imports=imports, code=code, timeout=timeout)

    def versions(self) -> dict[str, str]:
        """Return detected Lean and Lake versions."""
        return {"lean": lean_version(), "lake": lake_version()}

    # --- internal helpers ---
    def _init_or_reuse(self) -> None:
        """Initialize project if needed or verify an existing Lake project."""
        if self.path.exists():
            if self._is_lake_project():
                return
            if any(self.path.iterdir()):
                raise ProjectInitError(
                    f"Directory {self.path} exists but is not a Lake project and not empty."
                )
            # Empty dir: `lake new` would fail if dir exists, so fall back to `lake init`.
            self._run(["lake", "init"], cwd=self.path)
        else:
            # Create parent dirs then run `lake new` in parent.
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._run(["lake", "new", self.name], cwd=self.path.parent)

        if not self._is_lake_project():
            raise ProjectInitError(
                f"Expected Lake files not found in {self.path}. Initialization may have failed."
            )

    def _is_lake_project(self) -> bool:
        """Return True if lakefile.lean exists in the project root."""
        return self.lakefile.exists()

    def _run(self, args: list[str], *, cwd: Path) -> CompletedProcess[str]:
        """Run a command, raising ProjectInitError on failure."""
        proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise ProjectInitError(
                f"Command {' '.join(args)} failed (exit {proc.returncode}).\n"
                f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
            )
        return proc

