"""
Data models for analytics pipeline.

All models use Pydantic for validation and serialization.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class RepositoryMetadata(BaseModel):
    """Repository metadata."""

    # Identifiers
    codebase_id: str  # UUID string
    repository_name: str
    owner: str
    full_name: str

    # Basic metadata
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime | None
    default_branch: str

    # Repository characteristics
    primary_language: str | None
    languages: dict[str, int]  # language -> bytes
    size_kb: int

    # Status flags
    is_fork: bool
    is_archived: bool

    # Collection metadata
    collected_at: datetime
    collection_version: str = "1.0"


class FileChange(BaseModel):
    """File-level changes within a commit."""

    filename: str
    status: str  # "added", "deleted", "modified", "renamed"
    additions: int
    deletions: int
    changes: int
    previous_filename: str | None = None  # For renamed files

    # SLOC fields
    patch: str | None = None  # Raw git diff patch
    addition_bytes: int = 0  # UTF-8 bytes added
    deletion_bytes: int = 0  # UTF-8 bytes deleted
    patch_bytes: int = 0  # Total bytes (addition_bytes + deletion_bytes)
    net_bytes: int = 0  # Net byte change (addition_bytes - deletion_bytes)
    file_sloc: int = 0  # SLOC for this file (patch_bytes / 50)


class CommitRecord(BaseModel):
    """Commit data for storage."""

    # Identifiers
    commit_sha: str
    codebase_id: str  # UUID string
    branch_name: str

    # Temporal
    committed_at: datetime
    collected_at: datetime

    # Time bucketing (for partition pruning)
    commit_date: datetime | None = None
    commit_year: int | None = None
    commit_month: int | None = None
    commit_day: int | None = None

    # Author (from git)
    author_email: str
    author_name: str
    committer_email: str | None = None
    committer_name: str | None = None

    # Commit metadata
    message: str
    message_length: int = 0

    # Commit characteristics
    parent_count: int = 0
    is_merge_commit: bool = False
    files_changed: int = 0

    # Traditional line-based metrics
    additions_lines: int = 0
    deletions_lines: int = 0
    net_lines: int = 0
    churn_lines: int = 0

    # Byte-based SLOC metrics
    addition_bytes: int = 0
    deletion_bytes: int = 0
    patch_bytes: int = 0
    net_bytes: int = 0
    sloc: int = 0

    # Derived metrics
    bytes_per_line: float = 0.0
    commit_size_category: str = "small"
    is_refactor: bool = False

    # Collection metadata
    collection_version: str = "2.0"

    def model_post_init(self, __context) -> None:
        """Compute derived fields after initialization."""
        if self.commit_date is None and self.committed_at:
            self.commit_date = self.committed_at.date()
        if self.commit_year is None and self.committed_at:
            self.commit_year = self.committed_at.year
        if self.commit_month is None and self.committed_at:
            self.commit_month = self.committed_at.month
        if self.commit_day is None and self.committed_at:
            self.commit_day = self.committed_at.day
        if self.message_length == 0:
            self.message_length = len(self.message)
        if self.committer_email is None:
            self.committer_email = self.author_email
        if self.committer_name is None:
            self.committer_name = self.author_name


class BranchRecord(BaseModel):
    """Branch information for storage."""

    # Identifiers
    codebase_id: str
    branch_name: str

    # Branch metadata
    head_commit_sha: str
    divergence_point_sha: str | None = None
    parent_branch: str | None = None

    # Timestamps
    created_at: datetime | None = None
    last_commit_at: datetime

    # Line-based metrics
    current_lines: int = 0
    unique_lines: int = 0
    total_additions_lines: int = 0
    total_deletions_lines: int = 0

    # Byte-based SLOC metrics
    current_sloc: int = 0
    churn_sloc: int = 0
    unique_sloc: int = 0
    total_addition_bytes: int = 0
    total_deletion_bytes: int = 0

    # Branch stats
    total_commits: int = 0
    unique_commits: int = 0
    unique_contributors: int = 0
    total_files: int = 0

    # Branch state
    is_default_branch: bool = False
    is_active: bool = True
    is_merged: bool = False
    is_deleted: bool = False
    merged_at: datetime | None = None
    deleted_at: datetime | None = None

    # Analysis
    last_analyzed_at: datetime


class ContributorRecord(BaseModel):
    """Contributor statistics."""

    # Contributor identity
    contributor_email: str
    contributor_name: str
    codebase_id: str

    # Activity statistics
    total_commits: int
    first_commit_at: datetime
    last_commit_at: datetime

    # Windowed activity (30/90/365 days from latest commit)
    commits_last_30_days: int = 0
    commits_last_90_days: int = 0
    commits_last_365_days: int = 0

    # Branch activity
    branches_contributed_to: list[str] = []
    primary_branch: str = "main"
    branches_count: int = 1

    # Line-based metrics
    total_additions_lines: int = 0
    total_deletions_lines: int = 0
    avg_commit_size_lines: float = 0.0

    # Byte-based metrics
    total_sloc_contributed: int = 0
    total_addition_bytes: int = 0
    total_deletion_bytes: int = 0
    avg_commit_size_sloc: float = 0.0

    # Collection metadata
    collected_at: datetime


class IngestionSummary(BaseModel):
    """Summary of completed ingestion."""

    # Repository
    codebase_id: str  # UUID string
    repository_name: str

    # Statistics
    total_commits: int
    total_contributors: int
    first_commit_at: datetime
    last_commit_at: datetime

    # Optional branch info
    branches: int = 0

