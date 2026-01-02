class LeanPyError(Exception):
    """Base error for leanpy."""


class LeanNotFound(LeanPyError):
    """Raised when lean binary is not available."""


class LakeNotFound(LeanPyError):
    """Raised when lake binary is not available."""


class ProjectInitError(LeanPyError):
    """Raised when a project cannot be initialized or reused."""


class DependencyError(LeanPyError):
    """Raised when dependency installation fails."""


class ExecutionError(LeanPyError):
    """Raised when running Lean code fails."""

