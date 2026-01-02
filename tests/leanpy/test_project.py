import pytest

from leanpy import LeanProject
from leanpy.errors import ProjectInitError


def test_reuse_existing_lake_project(tmp_path):
    """
    GIVEN an existing Lake project,
    WHEN LeanProject is constructed again on the same path,
    THEN it should reuse the project and leave lakefile.lean intact.
    """
    project1 = LeanProject(tmp_path / "proj")
    assert (project1.path / "lakefile.lean").exists() or (project1.path / "lakefile.toml").exists()
    project2 = LeanProject(project1.path)
    assert (project2.path / "lakefile.lean").exists() or (project2.path / "lakefile.toml").exists()
    project1.remove()


def test_empty_dir_runs_lake_init(tmp_path):
    """
    GIVEN an existing empty directory,
    WHEN LeanProject is constructed,
    THEN it should initialize a Lake project (lakefile.lean present).
    """
    project = LeanProject(tmp_path)
    assert (project.path / "lakefile.lean").exists() or (project.path / "lakefile.toml").exists()
    project.remove()


def test_non_lake_non_empty_raises(tmp_path):
    """
    GIVEN a non-empty directory without Lake files,
    WHEN LeanProject is constructed,
    THEN it should raise ProjectInitError to avoid corrupting the directory.
    """
    (tmp_path / "something.txt").write_text("data", encoding="utf-8")
    with pytest.raises(ProjectInitError):
        LeanProject(tmp_path)


def test_clone_project(tmp_path):
    """
    GIVEN an existing Lake project,
    WHEN clone is called with a new destination,
    THEN the file structure should be copied and the new project should initialize.
    """
    project = LeanProject(tmp_path / "proj_clone_src")
    (project.path / "src" / "Demo.lean").parent.mkdir(parents=True, exist_ok=True)
    (project.path / "src" / "Demo.lean").write_text("def demo : Nat := 1", encoding="utf-8")

    clone_path = tmp_path / "proj_clone_dst"
    try:
        cloned = project.clone(clone_path, new_name="cloned_proj")
        assert (clone_path / "lakefile.lean").exists() or (clone_path / "lakefile.toml").exists()
        assert (clone_path / "src" / "Demo.lean").exists()
        assert cloned.path == clone_path.resolve()
    finally:
        project.remove()
        cloned.remove()

