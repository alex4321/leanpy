from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess

from .env import lake_supports_add
from .errors import DependencyError


@dataclass
class LeanDependencyConfig:
    """Configuration for a Lake dependency."""

    scope: str
    name: str
    version: str | None = None
    cache: bool = False

    @property
    def identifier(self) -> str:
        """
        Return the Lake package identifier, e.g. 'scope/name' or 'scope/name@v'.
        """
        base = f"{self.scope}/{self.name}"
        return f"{base}@{self.version}" if self.version else base


def install_dependency(project_path: Path, dep: LeanDependencyConfig) -> None:
    """
    Install a dependency into the project using Lake.

    Prefer editing lakefile.toml (Lake 5) when present; otherwise, fall back to
    `lake add` if supported. Runs `lake update` afterwards. If `dep.cache` is
    True, attempts to prefetch cached artifacts via `lake exe cache get`
    (best-effort).
    """
    lakefile_toml = project_path / "lakefile.toml"
    if lakefile_toml.exists():
        _write_dependency_toml(lakefile_toml, dep)
    elif lake_supports_add():
        _run(["lake", "add", dep.identifier], cwd=project_path)
    else:
        raise DependencyError(
            "Cannot install dependency: `lakefile.toml` not found and `lake add` "
            "is not supported by this Lake version."
        )

    _run(["lake", "update"], cwd=project_path)

    if dep.cache:
        # Attempt to prefetch cache; ignore failures.
        subprocess.run(
            ["lake", "exe", "cache", "get"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )


def _run(args: list[str], *, cwd: Path) -> CompletedProcess[str]:
    """Run a command and raise DependencyError on non-zero exit."""
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise DependencyError(
            f"Command {' '.join(args)} failed (exit {proc.returncode}).\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    return proc


def _write_dependency_toml(lakefile: Path, dep: LeanDependencyConfig) -> None:
    """Append dependency entry to lakefile.toml if not already present."""
    text = lakefile.read_text(encoding="utf-8")
    marker = f"[dependencies.{dep.name}]"
    if marker in text:
        return

    lines = []
    if not text.endswith("\n"):
        lines.append("\n")
    lines.append(marker)
    git_url = f"https://github.com/{dep.scope}/{dep.name}.git"
    lines.append(f'git = "{git_url}"')
    if dep.version:
        lines.append(f'branch = "{dep.version}"')
    lines.append("")  # trailing newline

    lakefile.write_text(text + "\n".join(lines), encoding="utf-8")

