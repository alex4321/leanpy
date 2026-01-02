import hashlib

import pytest

from leanpy import LeanProject
from leanpy.errors import ExecutionError
from leanpy.runner import RunResult


def test_run_code_success(tmp_path):
    """
    GIVEN a real Lake project and valid Lean snippet,
    WHEN run_code executes it,
    THEN it should emit stdout from Lean, exit with 0, and write the hashed temp file.
    """
    project = LeanProject(tmp_path / "proj")
    try:
        imports = []
        code = "#eval 1 + 1"
        result = project.run(imports=imports, code=code, timeout=30)

        digest = hashlib.sha1(("\n".join(imports) + "\n" + code).encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
        expected_file = project.path / ".leanpy" / f"run_{digest}.lean"

        assert isinstance(result, RunResult)
        assert result.returncode == 0
        assert "2" in result.stdout
        assert expected_file.exists()
        content = expected_file.read_text(encoding="utf-8")
        assert "#eval 1 + 1" in content
    finally:
        project.remove()


def test_run_code_failure(tmp_path):
    """
    GIVEN a real Lake project and broken Lean snippet,
    WHEN run_code executes it,
    THEN it should raise ExecutionError with captured stdout/stderr context.
    """
    project = LeanProject(tmp_path / "proj_fail")
    try:
        with pytest.raises(ExecutionError) as excinfo:
            project.run(imports=[], code="def bad : Bool := nope", timeout=30)
        msg = str(excinfo.value)
        assert "Lean exited" in msg
        assert "nope" in msg
    finally:
        project.remove()

