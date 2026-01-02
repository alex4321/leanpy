import pytest

from leanpy.deps import LeanDependencyConfig, install_dependency
from leanpy.errors import DependencyError, ProjectInitError
from leanpy import LeanProject

def test_dependency_identifier_format():
    """Ensure identifier formatting concatenates scope/name and optional version."""
    dep = LeanDependencyConfig(scope="org", name="pkg")
    assert dep.identifier == "org/pkg"
    dep2 = LeanDependencyConfig(scope="org", name="pkg", version="1.2.3")
    assert dep2.identifier == "org/pkg@1.2.3"


def test_install_dependency_real(monkeypatch, tmp_path):
    """
    Integration test: install a dependency in a real Lake project.
    Supports both Lake 4 (lake add) and Lake 5 (lakefile.toml edit + update).
    """
    try:
        project = LeanProject(tmp_path / "proj_dep")
    except ProjectInitError as exc:
        pytest.fail(f"lake init failed: {exc}")
    try:
        dep = LeanDependencyConfig(scope="leanprover-community", name="mathlib", cache=False)
        try:
            install_dependency(project.path, dep)
        except DependencyError as exc:
            # If both mechanisms fail, surface a clear assertion.
            pytest.fail(f"Dependency installation failed: {exc}")

        manifest = project.path / "lake-manifest.json"
        assert manifest.exists(), "lake-manifest.json should be present after install"
        manifest_text = manifest.read_text(encoding="utf-8")
        lakefile_text = (project.path / "lakefile.toml").read_text(encoding="utf-8")
        assert ("mathlib" in manifest_text) or ("mathlib" in lakefile_text)

        # Rehydrate project from disk and confirm dependencies list is populated.
        new_project = LeanProject(project.path)
        assert any(d.name == "mathlib" for d in new_project.dependencies)
        new_project.remove()
    finally:
        project.remove()

