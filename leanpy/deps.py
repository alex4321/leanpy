from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
import tomllib

from .errors import DependencyError


@dataclass(frozen=True)
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

    Writes a `[[require]]` entry to lakefile.toml (creating the file if missing),
    then runs `lake update`. If `dep.cache` is True, attempts to prefetch cached
    artifacts via `lake exe cache get` (best-effort).
    """
    lakefile_toml = project_path / "lakefile.toml"
    if not lakefile_toml.exists():
        lakefile_toml.write_text("[package]\n", encoding="utf-8")

    _write_dependency_toml(lakefile_toml, dep)

    def update_with_fallback() -> None:
        try:
            _run(["lake", "update", "--reconfigure"], cwd=project_path)
        except DependencyError as exc:
            msg = str(exc)
            if "--reconfigure" in msg or "unknown option" in msg or "unrecognized option" in msg:
                _run(["lake", "update"], cwd=project_path)
            else:
                raise

    update_with_fallback()

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
    """
    Append `[[require]]` dependency entry to lakefile.toml if not already present.

    Uses tomllib for reliable parsing to detect existing entries instead of
    relying on string search.
    """
    text = lakefile.read_text(encoding="utf-8")
    try:
        toml_data = tomllib.loads(text) if text.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise DependencyError(f"Invalid TOML in {lakefile}: {exc}") from exc

    if _dependency_exists(toml_data, dep):
        return

    lines = []
    if text and not text.endswith("\n"):
        lines.append("")
    lines.append("[[require]]")
    lines.append(f'name = "{dep.name}"')
    lines.append(f'scope = "{dep.scope}"')
    if dep.version:
        lines.append(f'rev = "{dep.version}"')
    lines.append("")  # trailing newline

    lakefile.write_text(text + "\n".join(lines), encoding="utf-8")


def _dependency_exists(toml_data: dict[str, Any], dep: LeanDependencyConfig) -> bool:
    """Return True if dependency already declared in [[require]] or [dependencies.*]."""
    require_entries = toml_data.get("require", [])
    if isinstance(require_entries, dict):
        require_entries = [require_entries]
    for entry in require_entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("name") == dep.name and entry.get("scope") == dep.scope:
            version = entry.get("rev") or entry.get("branch") or entry.get("tag")
            if dep.version is None or dep.version == version:
                return True

    dependencies_table = toml_data.get("dependencies") or {}
    if isinstance(dependencies_table, dict):
        existing_dep = dependencies_table.get(dep.name)
        if isinstance(existing_dep, dict):
            version = (
                existing_dep.get("rev")
                or existing_dep.get("branch")
                or existing_dep.get("tag")
            )
            scope = existing_dep.get("scope", "unknown")
            if scope == dep.scope and (dep.version is None or dep.version == version):
                return True

    return False

