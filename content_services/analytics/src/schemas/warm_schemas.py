"""
PyArrow schema definitions for warm analytics layer (Parquet).

The warm layer stores commit-level and contributor-level data optimized for
analytical queries. Supports dual SLOC metrics and branch tracking.

Version: 2.0
"""

import pyarrow as pa

WARM_SCHEMA_VERSION = "2.0"

# Commits table schema
COMMITS_SCHEMA = pa.schema([
    # Identity
    pa.field("commit_sha", pa.string(), nullable=False),
    pa.field("codebase_id", pa.string(), nullable=False),
    pa.field("branch_name", pa.string(), nullable=False),

    # Temporal
    pa.field("committed_at", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("collected_at", pa.timestamp("us", tz="UTC"), nullable=False),

    # Time bucketing (for partition pruning)
    pa.field("commit_date", pa.date32(), nullable=False),
    pa.field("commit_year", pa.int16(), nullable=False),
    pa.field("commit_month", pa.int8(), nullable=False),
    pa.field("commit_day", pa.int8(), nullable=False),

    # Author (from git)
    pa.field("author_email", pa.string(), nullable=False),
    pa.field("author_name", pa.string(), nullable=False),
    pa.field("committer_email", pa.string(), nullable=False),
    pa.field("committer_name", pa.string(), nullable=False),

    # Commit metadata
    pa.field("message", pa.string(), nullable=False),
    pa.field("message_length", pa.int32(), nullable=False),

    # Commit characteristics
    pa.field("parent_count", pa.int8(), nullable=False),
    pa.field("is_merge_commit", pa.bool_(), nullable=False),
    pa.field("files_changed", pa.int32(), nullable=False),

    # Traditional line-based metrics
    pa.field("additions_lines", pa.int32(), nullable=False),
    pa.field("deletions_lines", pa.int32(), nullable=False),
    pa.field("net_lines", pa.int32(), nullable=False),
    pa.field("churn_lines", pa.int32(), nullable=False),

    # Byte-based SLOC metrics
    pa.field("addition_bytes", pa.int64(), nullable=False),
    pa.field("deletion_bytes", pa.int64(), nullable=False),
    pa.field("patch_bytes", pa.int64(), nullable=False),
    pa.field("net_bytes", pa.int64(), nullable=False),
    pa.field("sloc", pa.int64(), nullable=False),

    # Derived metrics
    pa.field("bytes_per_line", pa.float32(), nullable=False),
    pa.field("commit_size_category", pa.string(), nullable=False),
    pa.field("is_refactor", pa.bool_(), nullable=False),

    # Collection metadata
    pa.field("collection_version", pa.string(), nullable=False)
])

# Contributors table schema
CONTRIBUTORS_SCHEMA = pa.schema([
    pa.field("codebase_id", pa.string(), nullable=False),
    pa.field("contributor_email", pa.string(), nullable=False),
    pa.field("contributor_name", pa.string(), nullable=False),

    # Activity stats
    pa.field("total_commits", pa.int32(), nullable=False),
    pa.field("first_commit_at", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("last_commit_at", pa.timestamp("us", tz="UTC"), nullable=False),

    # Branch activity
    pa.field("branches_contributed_to", pa.list_(pa.string()), nullable=False),
    pa.field("primary_branch", pa.string(), nullable=False),
    pa.field("branches_count", pa.int32(), nullable=False),

    # Windowed activity
    pa.field("commits_last_30_days", pa.int32(), nullable=False),
    pa.field("commits_last_90_days", pa.int32(), nullable=False),
    pa.field("commits_last_365_days", pa.int32(), nullable=False),

    # Traditional line-based contributions
    pa.field("total_additions_lines", pa.int64(), nullable=False),
    pa.field("total_deletions_lines", pa.int64(), nullable=False),
    pa.field("avg_commit_size_lines", pa.float32(), nullable=False),

    # Byte-based SLOC contributions
    pa.field("total_sloc_contributed", pa.int64(), nullable=False),
    pa.field("total_addition_bytes", pa.int64(), nullable=False),
    pa.field("total_deletion_bytes", pa.int64(), nullable=False),
    pa.field("avg_commit_size_sloc", pa.float32(), nullable=False),

    # Collection
    pa.field("collected_at", pa.timestamp("us", tz="UTC"), nullable=False)
])

# Branch snapshots schema
BRANCH_SNAPSHOTS_SCHEMA = pa.schema([
    pa.field("snapshot_id", pa.string(), nullable=False),
    pa.field("codebase_id", pa.string(), nullable=False),
    pa.field("branch_name", pa.string(), nullable=False),
    pa.field("snapshot_date", pa.date32(), nullable=False),
    pa.field("snapshot_type", pa.string(), nullable=False),  # scheduled/pre_rebase/post_rebase
    pa.field("branch_sha", pa.string(), nullable=True),  # HEAD at snapshot time
    pa.field("divergence_point_sha", pa.string(), nullable=True),

    # Unique metrics (commits unique to this branch)
    pa.field("unique_commits", pa.int32(), nullable=False),
    pa.field("unique_lines", pa.int64(), nullable=False),
    pa.field("unique_sloc", pa.int64(), nullable=False),
    pa.field("unique_addition_bytes", pa.int64(), nullable=False),
    pa.field("unique_contributors", pa.int32(), nullable=False),

    # Total metrics (all reachable commits)
    pa.field("total_commits", pa.int32(), nullable=False),
    pa.field("total_lines", pa.int64(), nullable=False),
    pa.field("total_sloc", pa.int64(), nullable=False),
    pa.field("total_addition_bytes", pa.int64(), nullable=False),
    pa.field("total_deletion_bytes", pa.int64(), nullable=False),
    pa.field("total_contributors", pa.int32(), nullable=False),
])

