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
from .project import LeanProject
from .runner import RunResult

__all__ = ["LeanProject", "LeanDependencyConfig", "RunResult"]

