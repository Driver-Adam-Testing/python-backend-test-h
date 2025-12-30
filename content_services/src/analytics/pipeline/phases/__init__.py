"""Pipeline phases module."""
from .clone import clone_repository, open_repository, cleanup_repository, CloneResult
from .extract import extract_commits, ExtractResult
from .branches import discover_branches, BranchesResult, BranchInfo

__all__ = [
    "clone_repository",
    "open_repository",
    "cleanup_repository",
    "CloneResult",
    "extract_commits",
    "ExtractResult",
    "discover_branches",
    "BranchesResult",
    "BranchInfo",
]

