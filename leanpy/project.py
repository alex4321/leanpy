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
        run_log: list[tuple[list[str], str, str, int]] = []
        if self.path.exists():
            if self._is_lake_project():
                return
            if any(self.path.iterdir()):
                raise ProjectInitError(
                    f"Directory {self.path} exists but is not a Lake project and not empty."
                )
            # Empty dir: `lake new` would fail if dir exists, so fall back to `lake init`.
            proc = self._run(["lake", "init"], cwd=self.path)
            run_log.append((["lake", "init"], proc.stdout, proc.stderr, proc.returncode))
        else:
            # Create parent dirs then run `lake new` in parent.
            self.path.parent.mkdir(parents=True, exist_ok=True)
            proc = self._run(["lake", "new", self.name], cwd=self.path.parent)
            run_log.append((["lake", "new", self.name], proc.stdout, proc.stderr, proc.returncode))

        if not self._is_lake_project():
            try:
                contents = sorted(p.name for p in self.path.iterdir())
                contents_str = ", ".join(contents) if contents else "(empty)"
            except Exception:
                contents_str = "(unreadable)"

            cmd_section = ""
            if run_log:
                cmd_lines = []
                for args, stdout, stderr, rc in run_log:
                    cmd_lines.append(
                        f"{' '.join(args)} (exit {rc})\nstdout:\n{stdout}\nstderr:\n{stderr}"
                    )
                cmd_section = "\nCommands run:\n" + "\n---\n".join(cmd_lines)

            raise ProjectInitError(
                f"Expected Lake files not found in {self.path}. Initialization may have failed. "
                f"Directory contents: {contents_str}.{cmd_section}"
            )

    def _is_lake_project(self) -> bool:
        """Return True if recognizable Lake project files exist."""
        return self.lakefile.exists() or (self.path / "lakefile.toml").exists()

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
        """Populate dependencies from lake-manifest.json or lakefile.toml if present."""
        manifest = self.path / "lake-manifest.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                packages = data.get("packages", [])
                for pkg in packages:
                    pkg_name = pkg.get("name")
                    if not pkg_name or pkg_name == self.name:
                        continue
                    scope, name = self._extract_scope_and_name(pkg)
                    dep = LeanDependencyConfig(scope=scope, name=name)
                    self._add_dependency_if_missing(dep)
            except Exception:
                pass

        lakefile_toml = self.path / "lakefile.toml"
        if lakefile_toml.exists():
            for dep in self._extract_from_toml(lakefile_toml):
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

    def _extract_from_toml(self, lakefile: Path) -> list[LeanDependencyConfig]:
        """Parse lakefile.toml dependencies (old [dependencies.*] and [[require]])."""
        text = lakefile.read_text(encoding="utf-8")
        deps: list[LeanDependencyConfig] = []
        current_dep: dict[str, str] | None = None
        mode_require = False

        def flush():
            nonlocal current_dep, mode_require
            if not current_dep:
                return
            name = current_dep.get("name")
            scope = current_dep.get("scope", "unknown")
            version = current_dep.get("rev") or current_dep.get("branch") or current_dep.get("tag")
            git_url = current_dep.get("git")
            if git_url and scope == "unknown":
                scope, name_from_git = self._scope_name_from_git(git_url, name or "")
                if name_from_git:
                    name = name_from_git
            if name:
                deps.append(LeanDependencyConfig(scope=scope, name=name, version=version))
            current_dep = None
            mode_require = False

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                flush()
                continue
            if stripped.startswith("[[require]]"):
                flush()
                mode_require = True
                current_dep = {}
                continue
            if stripped.startswith("[dependencies.") and stripped.endswith("]"):
                flush()
                mode_require = False
                name = stripped[len("[dependencies.") : -1]
                current_dep = {"name": name}
                continue
            if "=" not in stripped or current_dep is None:
                continue
            key, val = [part.strip() for part in stripped.split("=", 1)]
            val = val.strip().strip('"')
            current_dep[key] = val

        flush()
        return deps

    def _scope_name_from_git(self, git_url: str | None, fallback_name: str) -> tuple[str, str]:
        if git_url:
            parsed = urlparse(git_url)
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2:
                scope = parts[-2]
                repo = parts[-1].removesuffix(".git")
                return scope, repo
        return "unknown", fallback_name

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

