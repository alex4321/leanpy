import shutil

import pytest

from leanpy.deps import LeanDependencyConfig, install_dependency
from leanpy.errors import DependencyError
from leanpy import LeanProject

HAS_BINARIES = shutil.which("lean") and shutil.which("lake")
requires_lean = pytest.mark.skipif(not HAS_BINARIES, reason="requires lean/lake on PATH")


def test_dependency_identifier_format():
    """Ensure identifier formatting concatenates scope/name and optional version."""
    dep = LeanDependencyConfig(scope="org", name="pkg")
    assert dep.identifier == "org/pkg"
    dep2 = LeanDependencyConfig(scope="org", name="pkg", version="1.2.3")
    assert dep2.identifier == "org/pkg@1.2.3"


@requires_lean
def test_install_dependency_real(monkeypatch, tmp_path):
    """
    Integration test: install a dependency in a real Lake project.
    Requires Lean/Lake (and network if dependency fetch needs it).
    """
    project = LeanProject(tmp_path / "proj_dep")
    try:
        dep = LeanDependencyConfig(scope="leanprover-community", name="mathlib", cache=False)
        install_dependency(project.path, dep)

        manifest = project.path / "lake-manifest.json"
        assert manifest.exists(), "lake-manifest.json should be present after install"
        manifest_text = manifest.read_text(encoding="utf-8")
        assert "mathlib" in manifest_text

        # Rehydrate project from disk and confirm dependencies list is populated.
        new_project = LeanProject(project.path)
        assert any(d.name == "mathlib" for d in new_project.dependencies)
        new_project.remove()
    finally:
        project.remove()

