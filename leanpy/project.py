from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from typing import List, Optional
from urllib.parse import urlparse

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
        self._load_existing_dependencies()

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

    def remove(self) -> None:
        """Delete the project directory recursively (best-effort)."""
        shutil.rmtree(self.path, ignore_errors=True)

    def clone(self, new_dir: os.PathLike | str, new_name: Optional[str] = None) -> "LeanProject":
        """
        Copy the current project to `new_dir` and initialize a LeanProject there.

        Files are copied as-is; `new_name` overrides the inferred project name.
        """
        dest = Path(new_dir).expanduser().resolve()
        if dest.exists():
            raise ProjectInitError(f"Destination {dest} already exists; cannot clone.")
        try:
            shutil.copytree(self.path, dest)
        except Exception as exc:
            raise ProjectInitError(f"Failed to clone project to {dest}: {exc}") from exc
        return LeanProject(dest, name=new_name or dest.name)

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

    def _load_existing_dependencies(self) -> None:
        """Populate dependencies from lake-manifest.json if present."""
        manifest = self.path / "lake-manifest.json"
        if not manifest.exists():
            return
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            return
        packages = data.get("packages", [])
        for pkg in packages:
            pkg_name = pkg.get("name")
            if not pkg_name or pkg_name == self.name:
                continue
            scope, name = self._extract_scope_and_name(pkg)
            dep = LeanDependencyConfig(scope=scope, name=name)
            self._add_dependency_if_missing(dep)

    def _extract_scope_and_name(self, pkg: dict) -> tuple[str, str]:
        """Best-effort extraction of scope/name from manifest package entry."""
        url = pkg.get("url") or pkg.get("git") or pkg.get("gitUrl") or ""
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) >= 2:
            scope = path_parts[-2]
            repo = path_parts[-1].removesuffix(".git")
            return scope, repo
        # Fallback: unknown scope, keep manifest name as repo.
        name = pkg.get("name", "unknown")
        return "unknown", name

    def _add_dependency_if_missing(self, dep: LeanDependencyConfig) -> None:
        """Avoid duplicate dependency entries."""
        for existing in self.dependencies:
            if (
                existing.scope == dep.scope
                and existing.name == dep.name
                and existing.version == dep.version
            ):
                return
        self.dependencies.append(dep)

