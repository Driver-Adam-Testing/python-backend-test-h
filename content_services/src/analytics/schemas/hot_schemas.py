"""
DuckDB schema definitions for hot aggregates layer.

The hot layer provides pre-aggregated metrics optimized for fast querying and
dashboard visualization. All schemas support dual SLOC metrics (line-based and
byte-based) and comprehensive branch tracking.

Version: 2.0
"""

HOT_SCHEMA_VERSION = "2.0"

# SQL DDL statements
REPOSITORY_METRICS_DDL = """
CREATE TABLE IF NOT EXISTS repository_metrics (
    codebase_id VARCHAR(36) PRIMARY KEY,
    repository_name VARCHAR NOT NULL,
    full_name VARCHAR NOT NULL,
    owner VARCHAR NOT NULL,

    -- Traditional line-based metrics
    total_lines BIGINT NOT NULL DEFAULT 0,
    total_additions_lines BIGINT NOT NULL DEFAULT 0,
    total_deletions_lines BIGINT NOT NULL DEFAULT 0,

    -- Byte-based SLOC metrics (Driver method)
    total_sloc BIGINT NOT NULL DEFAULT 0,
    current_sloc BIGINT NOT NULL DEFAULT 0,
    total_addition_bytes BIGINT NOT NULL DEFAULT 0,
    total_deletion_bytes BIGINT NOT NULL DEFAULT 0,

    -- Metrics comparison
    avg_bytes_per_line FLOAT,

    -- Aggregates
    total_commits INTEGER NOT NULL DEFAULT 0,
    total_contributors INTEGER NOT NULL DEFAULT 0,
    total_branches INTEGER NOT NULL DEFAULT 0,
    total_files INTEGER NOT NULL DEFAULT 0,

    -- Branch info
    default_branch VARCHAR NOT NULL,
    primary_language VARCHAR,

    -- Time range
    first_commit_at TIMESTAMP,
    last_commit_at TIMESTAMP,

    -- Collection metadata
    collected_at TIMESTAMP NOT NULL,
    last_updated_at TIMESTAMP NOT NULL,
    collection_version VARCHAR NOT NULL DEFAULT '2.0'
);
"""

DAILY_METRICS_DDL = """
CREATE TABLE IF NOT EXISTS daily_metrics (
    codebase_id VARCHAR(36) NOT NULL,
    date DATE NOT NULL,

    -- Line-based daily deltas
    additions_lines INTEGER NOT NULL DEFAULT 0,
    deletions_lines INTEGER NOT NULL DEFAULT 0,
    net_change_lines INTEGER NOT NULL DEFAULT 0,
    churn_lines INTEGER NOT NULL DEFAULT 0,
    cumulative_lines BIGINT NOT NULL DEFAULT 0,

    -- Byte-based daily deltas
    addition_bytes BIGINT NOT NULL DEFAULT 0,
    deletion_bytes BIGINT NOT NULL DEFAULT 0,
    net_bytes BIGINT NOT NULL DEFAULT 0,
    patch_bytes BIGINT NOT NULL DEFAULT 0,
    cumulative_sloc BIGINT NOT NULL DEFAULT 0,

    -- Activity
    commits_count INTEGER NOT NULL DEFAULT 0,
    active_contributors INTEGER NOT NULL DEFAULT 0,
    files_changed INTEGER NOT NULL DEFAULT 0,

    PRIMARY KEY (codebase_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_date
ON daily_metrics(codebase_id, date);
"""

MONTHLY_METRICS_DDL = """
CREATE TABLE IF NOT EXISTS monthly_metrics (
    codebase_id VARCHAR(36) NOT NULL,
    year_month VARCHAR(7) NOT NULL,  -- YYYY-MM format

    -- Aggregates
    commits_count INTEGER NOT NULL DEFAULT 0,
    unique_contributors INTEGER NOT NULL DEFAULT 0,

    -- Line-based
    additions_lines INTEGER NOT NULL DEFAULT 0,
    deletions_lines INTEGER NOT NULL DEFAULT 0,
    net_lines INTEGER NOT NULL DEFAULT 0,

    -- Byte-based
    addition_bytes BIGINT NOT NULL DEFAULT 0,
    deletion_bytes BIGINT NOT NULL DEFAULT 0,
    net_sloc BIGINT NOT NULL DEFAULT 0,

    -- Commit size stats
    avg_commit_size_lines FLOAT,
    avg_commit_size_sloc FLOAT,
    max_commit_size_lines INTEGER,
    max_commit_size_sloc INTEGER,

    PRIMARY KEY (codebase_id, year_month)
);
"""

BRANCH_SUMMARY_DDL = """
CREATE TABLE IF NOT EXISTS branch_summary (
    codebase_id VARCHAR(36) NOT NULL,
    branch_name VARCHAR NOT NULL,

    -- Branch metadata
    head_commit_sha VARCHAR NOT NULL,
    divergence_point_sha VARCHAR,
    parent_branch VARCHAR,

    -- Timestamps
    created_at TIMESTAMP,
    last_commit_at TIMESTAMP NOT NULL,

    -- Traditional line-based metrics
    current_lines BIGINT NOT NULL DEFAULT 0,
    unique_lines BIGINT NOT NULL DEFAULT 0,
    total_additions_lines BIGINT NOT NULL DEFAULT 0,
    total_deletions_lines BIGINT NOT NULL DEFAULT 0,

    -- Byte-based SLOC metrics
    current_sloc BIGINT NOT NULL DEFAULT 0,
    unique_sloc BIGINT NOT NULL DEFAULT 0,
    total_addition_bytes BIGINT NOT NULL DEFAULT 0,
    total_deletion_bytes BIGINT NOT NULL DEFAULT 0,

    -- Branch stats
    total_commits INTEGER NOT NULL DEFAULT 0,
    unique_commits INTEGER NOT NULL DEFAULT 0,
    unique_contributors INTEGER NOT NULL DEFAULT 0,
    total_files INTEGER NOT NULL DEFAULT 0,

    -- Branch state
    is_default_branch BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_merged BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    merged_at TIMESTAMP,
    deleted_at TIMESTAMP,

    -- Analysis
    last_analyzed_at TIMESTAMP NOT NULL,

    PRIMARY KEY (codebase_id, branch_name)
);

CREATE INDEX IF NOT EXISTS idx_branch_summary_state
ON branch_summary(codebase_id, is_active, is_deleted);
"""

BRANCH_METRICS_DDL = """
CREATE TABLE IF NOT EXISTS branch_metrics (
    codebase_id VARCHAR(36) NOT NULL,
    branch_name VARCHAR NOT NULL,

    -- Branch metadata
    head_commit_sha VARCHAR NOT NULL,
    divergence_point_sha VARCHAR,
    parent_branch VARCHAR,

    -- Timestamps
    created_at TIMESTAMP,
    last_commit_at TIMESTAMP NOT NULL,

    -- Traditional line-based metrics
    current_lines BIGINT NOT NULL DEFAULT 0,
    unique_lines BIGINT NOT NULL DEFAULT 0,
    total_additions_lines BIGINT NOT NULL DEFAULT 0,
    total_deletions_lines BIGINT NOT NULL DEFAULT 0,

    -- Byte-based SLOC metrics
    current_sloc BIGINT NOT NULL DEFAULT 0,
    churn_sloc BIGINT NOT NULL DEFAULT 0,
    unique_sloc BIGINT NOT NULL DEFAULT 0,
    total_addition_bytes BIGINT NOT NULL DEFAULT 0,
    total_deletion_bytes BIGINT NOT NULL DEFAULT 0,

    -- Branch stats
    total_commits INTEGER NOT NULL DEFAULT 0,
    unique_commits INTEGER NOT NULL DEFAULT 0,
    unique_contributors INTEGER NOT NULL DEFAULT 0,
    total_files INTEGER NOT NULL DEFAULT 0,

    -- Branch state
    is_default_branch BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_merged BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    merged_at TIMESTAMP,
    deleted_at TIMESTAMP,

    -- Analysis
    last_analyzed_at TIMESTAMP NOT NULL,

    PRIMARY KEY (codebase_id, branch_name)
);

CREATE INDEX IF NOT EXISTS idx_branch_metrics_state
ON branch_metrics(codebase_id, is_active, is_deleted);
"""

BRANCH_STATE_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS branch_state_history (
    codebase_id VARCHAR(36) NOT NULL,
    branch_name VARCHAR NOT NULL,
    observed_at TIMESTAMP NOT NULL,

    -- Branch pointer
    head_commit_sha VARCHAR NOT NULL,

    -- Lineage
    divergence_point_sha VARCHAR,
    parent_branch VARCHAR,

    -- Reachability
    commits_reachable INTEGER NOT NULL DEFAULT 0,
    unique_commits INTEGER NOT NULL DEFAULT 0,

    -- State
    branch_state VARCHAR NOT NULL,  -- active/merged/deleted/rebased/stale
    state_changed_at TIMESTAMP,
    event_type VARCHAR,  -- create/update/rebase/merge/delete/force_push

    -- Event details (JSON for flexibility)
    event_metadata VARCHAR,  -- JSON string

    PRIMARY KEY (codebase_id, branch_name, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_branch_state_history_state
ON branch_state_history(codebase_id, branch_state, observed_at);
"""

DIRECTORY_OWNERSHIP_DDL = """
CREATE TABLE IF NOT EXISTS directory_ownership (
    codebase_id VARCHAR(36) NOT NULL,
    directory_path VARCHAR NOT NULL,
    branch_name VARCHAR NOT NULL DEFAULT '',  -- Empty string = all branches
    total_commits INTEGER NOT NULL DEFAULT 0,
    total_sloc INTEGER NOT NULL DEFAULT 0,
    unique_contributors INTEGER NOT NULL DEFAULT 0,
    primary_owner_email VARCHAR,
    primary_owner_name VARCHAR,
    primary_owner_percentage DOUBLE,
    last_updated TIMESTAMP,
    PRIMARY KEY (codebase_id, directory_path, branch_name)
);

CREATE INDEX IF NOT EXISTS idx_directory_ownership_codebase
ON directory_ownership(codebase_id);

CREATE INDEX IF NOT EXISTS idx_directory_ownership_branch
ON directory_ownership(codebase_id, branch_name);
"""

DIRECTORY_CONTRIBUTORS_DDL = """
CREATE TABLE IF NOT EXISTS directory_contributors (
    codebase_id VARCHAR(36) NOT NULL,
    directory_path VARCHAR NOT NULL,
    branch_name VARCHAR NOT NULL DEFAULT '',  -- Empty string = all branches
    contributor_email VARCHAR NOT NULL,
    contributor_name VARCHAR NOT NULL,
    total_commits INTEGER NOT NULL DEFAULT 0,
    total_sloc INTEGER NOT NULL DEFAULT 0,
    ownership_percentage DOUBLE NOT NULL DEFAULT 0.0,
    first_commit_at TIMESTAMP,
    last_commit_at TIMESTAMP,
    active_days INTEGER,
    rank INTEGER,                  -- 1-10, top 10 only
    PRIMARY KEY (codebase_id, directory_path, branch_name, contributor_email)
);

CREATE INDEX IF NOT EXISTS idx_directory_contributors_codebase
ON directory_contributors(codebase_id);

CREATE INDEX IF NOT EXISTS idx_directory_contributors_rank
ON directory_contributors(codebase_id, directory_path, rank);
"""

# List of all DDL statements to execute
ALL_HOT_SCHEMAS = [
    REPOSITORY_METRICS_DDL,
    DAILY_METRICS_DDL,
    MONTHLY_METRICS_DDL,
    BRANCH_SUMMARY_DDL,
    BRANCH_METRICS_DDL,
    BRANCH_STATE_HISTORY_DDL,
    DIRECTORY_OWNERSHIP_DDL,
    DIRECTORY_CONTRIBUTORS_DDL,
]

