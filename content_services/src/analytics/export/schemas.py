"""Pydantic schemas for Driver JSON export."""
from datetime import datetime
from pydantic import BaseModel, Field


class OverviewJSON(BaseModel):
    """Schema for overview.json - codebase summary metrics."""
    codebase_id: str
    display_name: str
    repository_name: str
    full_name: str
    owner: str
    total_commits: int
    total_contributors: int
    total_branches: int
    # Traditional line-based metrics
    total_lines: int  # Traditional line count (current codebase size)
    total_additions_lines: int  # Total lines added over time (churn)
    total_deletions_lines: int  # Total lines deleted over time (churn)
    total_churn: int  # total_additions_lines + total_deletions_lines
    # Byte-based SLOC metrics
    total_sloc: int  # Churn-based SLOC (additions + deletions in bytes / 50)
    net_sloc: int  # Net SLOC (current codebase size)
    current_sloc: int  # Alias for net_sloc
    total_addition_bytes: int  # Total bytes added over time (churn)
    total_deletion_bytes: int  # Total bytes deleted over time (churn)
    avg_bytes_per_line: float | None  # Average bytes per line ratio
    total_files: int  # Total number of files
    default_branch: str
    primary_language: str | None
    first_commit_date: datetime | None
    last_commit_date: datetime | None
    collected_at: datetime  # When repository data was collected/ingested
    last_updated_at: datetime  # When this JSON was generated


class BranchEntry(BaseModel):
    name: str
    is_default: bool
    commits: int
    last_commit_date: datetime | None
    last_analyzed_at: datetime  # When branch metrics were computed
    status: str  # "active", "stale", "merged"
    # Branch metadata
    head_commit_sha: str = ""
    divergence_point_sha: str | None = None
    parent_branch: str | None = None
    created_at: datetime | None = None
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
    unique_commits: int = 0
    unique_contributors: int = 0
    total_files: int = 0
    # Branch state flags
    is_active: bool = True
    is_merged: bool = False
    is_deleted: bool = False
    merged_at: datetime | None = None
    deleted_at: datetime | None = None


class BranchesJSON(BaseModel):
    """Schema for branches.json"""
    codebase_id: str
    branches: list[BranchEntry]


class ContributorEntry(BaseModel):
    """Single contributor within a directory."""
    contributor_email: str
    contributor_name: str
    total_commits: int
    total_sloc: int
    ownership_percentage: float
    first_commit_at: datetime | None
    last_commit_at: datetime | None
    active_days: int


class DirectoryOwnership(BaseModel):
    """Ownership data for a single directory."""
    directory_path: str
    total_commits: int
    total_sloc: int
    unique_contributors: int
    primary_owner_email: str | None
    primary_owner_name: str | None
    primary_owner_percentage: float
    contributors: list[ContributorEntry]


class OwnershipJSON(BaseModel):
    """Schema for ownership.json - code ownership by directory."""
    codebase_id: str
    directories: list[DirectoryOwnership]


class ActivityEntry(BaseModel):
    date: str
    commits: int
    # Line-based metrics
    additions: int  # additions_lines
    deletions: int  # deletions_lines
    active_contributors: int = 0
    files_changed: int = 0
    cumulative_lines: int = 0
    # Byte-based metrics for SLOC calculation
    addition_bytes: int = 0
    deletion_bytes: int = 0
    net_bytes: int = 0
    patch_bytes: int = 0
    cumulative_sloc: int = 0


class ActivityJSON(BaseModel):
    """Schema for activity.json"""
    codebase_id: str
    daily_activity: list[ActivityEntry]


class MetadataJSON(BaseModel):
    """Schema for metadata.json - generation info."""
    codebase_id: str
    generated_at: datetime
    status: str  # "complete", "failed"
    generation_seconds: float


class CodebaseListEntry(BaseModel):
    codebase_id: str
    display_name: str
    total_commits: int
    current_sloc: int
    last_commit_date: datetime | None
    analytics_status: str
    # Additional fields for frontend Analytics table
    total_contributors: int = 0
    total_branches: int = 0
    primary_language: str | None = None
    total_churn: int = 0  # total_additions_lines + total_deletions_lines


class OrgSummaryJSON(BaseModel):
    """Schema for org_summary.json"""
    organization_id: str
    total_codebases: int
    codebases_with_analytics: int
    generated_at: datetime


class CodebasesListJSON(BaseModel):
    """Schema for codebases_list.json"""
    organization_id: str
    codebases: list[CodebaseListEntry]
    generated_at: datetime

