"""
Simple Lean/Lake project helper.

Usage example:
    from leanpy import LeanProject, LeanDependencyConfig
    project = LeanProject("/path/to/project", name="demo")
    dep = LeanDependencyConfig(scope="leanprover-community", name="mathlib", cache=True)
    project.install_dependency(dep)
    result = project.run(imports=["Mathlib"], code="def hello : String := \"hello\"")
"""

from .deps import LeanDependencyConfig
from .env import ensure_lake_installed, ensure_lean_installed, lake_supports_add
from .project import LeanProject
from .runner import RunResult

__all__ = ["LeanProject", "LeanDependencyConfig", "RunResult"]

# Proactively verify required binaries on import for early feedback.
ensure_lean_installed()
ensure_lake_installed()
