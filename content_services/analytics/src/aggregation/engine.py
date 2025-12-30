"""
Aggregation engine for pre-computing analytics in hot storage.

This module provides efficient aggregation of commit data from warm storage (Parquet)
into pre-computed metrics in hot storage (DuckDB) for sub-10ms query performance.
"""

import logging
from datetime import datetime
from pathlib import Path
import pandas as pd

from src.storage.hot_storage import HotStorage
from src.storage.parquet_storage import ParquetStorage

logger = logging.getLogger(__name__)


class AggregationEngine:
    """
    Build and maintain pre-computed aggregates in hot storage.

    The aggregation engine reads raw commit data from warm storage (Parquet)
    and builds pre-computed aggregates in hot storage (DuckDB) for fast queries.

    Example:
        >>> hot = HotStorage(Path('/data/hot/analytics.duckdb'))
        >>> warm = ParquetStorage(Path('/data/warm'))
        >>> engine = AggregationEngine(hot, warm)
        >>> engine.build_all_aggregates(codebase_id='uuid-here')
    """

    def __init__(self, hot_storage: HotStorage, warm_storage: ParquetStorage, cold_storage: ParquetStorage = None):
        """Initialize aggregation engine.

        Args:
            hot_storage: HotStorage instance (DuckDB)
            warm_storage: ParquetStorage instance (Parquet warm layer)
            cold_storage: ParquetStorage instance (Parquet cold layer, optional)
        """
        self.hot = hot_storage
        self.warm = warm_storage
        self.cold = cold_storage if cold_storage else warm_storage
        logger.info("Initialized AggregationEngine")

    def build_all_aggregates(self, codebase_id: str, force_rebuild: bool = False) -> dict:
        """
        Build all aggregates for a repository.

        Args:
            codebase_id: Repository identifier
            force_rebuild: Force full rebuild even if aggregates exist

        Returns:
            Dictionary with aggregation statistics

        Raises:
            ValueError: If no commit data found for repository
        """
        logger.info(f"Building all aggregates for repo {codebase_id} (force_rebuild={force_rebuild})")

        # Check if aggregates exist
        if not force_rebuild and self._aggregates_exist(codebase_id):
            logger.warning(f"Aggregates exist for repo {codebase_id}, use force_rebuild=True")
            return {
                'status': 'skipped',
                'reason': 'aggregates_exist',
                'codebase_id': codebase_id
            }

        # Load raw data from warm storage
        commits_df = self._load_commits(codebase_id)

        if commits_df.empty:
            logger.warning(f"No commits found for repo {codebase_id}")
            raise ValueError(f"No commit data found for repository {codebase_id}")

        logger.info(f"Loaded {len(commits_df)} commits for aggregation")

        # Build each aggregate type
        stats = {
            'codebase_id': codebase_id,
            'commits_processed': len(commits_df),
            'aggregates_built': []
        }

        try:
            self._build_repository_aggregate(codebase_id, commits_df)
            stats['aggregates_built'].append('repository')

            self._build_daily_aggregates(codebase_id, commits_df)
            stats['aggregates_built'].append('daily')

            self._build_monthly_aggregates(codebase_id, commits_df)
            stats['aggregates_built'].append('monthly')

            stats['status'] = 'success'
            stats['timestamp'] = datetime.now().isoformat()

            logger.info(f"Successfully built all aggregates for repo {codebase_id}")
            return stats

        except Exception as e:
            logger.error(f"Failed to build aggregates for repo {codebase_id}: {e}")
            stats['status'] = 'error'
            stats['error'] = str(e)
            raise

    def refresh_branch_metrics(self, codebase_id: str, branch_name: str = None) -> dict:
        """
        Refresh branch metrics from warm data.

        Args:
            codebase_id: Repository identifier
            branch_name: Specific branch to refresh (None = all branches)

        Returns:
            Dictionary with refresh statistics
        """
        logger.info(f"Refreshing branch metrics for repo {codebase_id} (branch={branch_name})")

        filters = None
        if branch_name:
            filters = [('branch_name', '=', branch_name)]

        # Load branch commits
        commits_df = self._load_commits(codebase_id, filters=filters)

        if commits_df.empty:
            logger.warning(f"No commits found for branch refresh (repo={codebase_id}, branch={branch_name})")
            return {
                'status': 'skipped',
                'reason': 'no_commits',
                'codebase_id': codebase_id,
                'branch_name': branch_name
            }

        stats = {
            'codebase_id': codebase_id,
            'branch_name': branch_name,
            'commits_processed': len(commits_df),
            'branches_updated': []
        }

        try:
            # Group by branch and calculate metrics
            for branch, branch_df in commits_df.groupby('branch_name'):
                branch_metrics = self._calculate_branch_metrics(codebase_id, branch, branch_df)
                self.hot.upsert_branch_metrics(branch_metrics)
                stats['branches_updated'].append(branch)

            stats['status'] = 'success'
            stats['timestamp'] = datetime.now().isoformat()

            logger.info(f"Refreshed {len(stats['branches_updated'])} branches for repo {codebase_id}")
            return stats

        except Exception as e:
            logger.error(f"Failed to refresh branch metrics: {e}")
            stats['status'] = 'error'
            stats['error'] = str(e)
            raise

    def _load_commits(self, codebase_id: str, filters: list[tuple] = None) -> pd.DataFrame:
        """Load commits from warm storage.

        Args:
            codebase_id: Repository ID
            filters: Optional PyArrow filters

        Returns:
            DataFrame of commits
        """
        logger.debug(f"Loading commits from warm storage for repo {codebase_id}")

        # Select columns needed for aggregation
        columns = [
            'commit_sha',
            'committed_at',
            'branch_name',
            'additions_lines',
            'deletions_lines',
            'net_lines',
            'churn_lines',
            'addition_bytes',
            'deletion_bytes',
            'patch_bytes',
            'net_bytes',
            'sloc',
            'bytes_per_line',
            'author_email',
            'files_changed'
        ]

        commits_df = self.warm.read_commits(codebase_id, columns=columns, filters=filters)

        if not commits_df.empty:
            # Ensure datetime type
            commits_df['committed_at'] = pd.to_datetime(commits_df['committed_at'])
            logger.info(f"Loaded {len(commits_df)} commits from warm storage")
        else:
            logger.warning(f"No commits found in warm storage for repo {codebase_id}")

        return commits_df

    def _build_repository_aggregate(self, codebase_id: str, commits_df: pd.DataFrame) -> None:
        """Build repository-level aggregate."""
        logger.debug(f"Building repository aggregate for repo {codebase_id}")

        # Deduplicate commits by SHA (same commit may appear on multiple branches)
        unique_commits = commits_df.drop_duplicates(subset=['commit_sha'])

        # Calculate metrics
        total_commits = len(unique_commits)

        # Line-based SLOC (net additions - deletions)
        total_lines = unique_commits['net_lines'].sum()
        total_additions_lines = unique_commits['additions_lines'].sum()
        total_deletions_lines = unique_commits['deletions_lines'].sum()

        # Byte-based SLOC
        total_sloc = unique_commits['sloc'].sum()
        total_addition_bytes = unique_commits['addition_bytes'].sum()
        total_deletion_bytes = unique_commits['deletion_bytes'].sum()

        # Average bytes per line
        avg_bytes_per_line = (
            total_addition_bytes / total_additions_lines
            if total_additions_lines > 0 else 0.0
        )

        # Unique counts
        total_contributors = unique_commits['author_email'].nunique()
        branch_count = commits_df['branch_name'].nunique()

        # Date range
        first_commit_at = unique_commits['committed_at'].min()
        last_commit_at = unique_commits['committed_at'].max()

        # Total files (approximate - count unique file changes)
        total_files = unique_commits['files_changed'].sum()

        # Default branch (most common branch)
        default_branch = commits_df['branch_name'].mode()[0] if not commits_df.empty else 'main'

        # Store aggregate (convert numpy types to Python types)
        metrics = {
            'codebase_id': codebase_id,
            'repository_name': f'repo_{codebase_id[:8]}',
            'full_name': f'owner/repo_{codebase_id[:8]}',
            'owner': 'owner',
            'total_lines': int(total_lines),
            'total_additions_lines': int(total_additions_lines),
            'total_deletions_lines': int(total_deletions_lines),
            'total_sloc': int(total_sloc),
            'current_sloc': int(total_sloc),
            'total_addition_bytes': int(total_addition_bytes),
            'total_deletion_bytes': int(total_deletion_bytes),
            'avg_bytes_per_line': float(avg_bytes_per_line),
            'total_commits': int(total_commits),
            'total_contributors': int(total_contributors),
            'total_branches': int(branch_count),
            'total_files': int(total_files),
            'default_branch': str(default_branch),
            'primary_language': None,
            'first_commit_at': first_commit_at.to_pydatetime() if hasattr(first_commit_at, 'to_pydatetime') else first_commit_at,
            'last_commit_at': last_commit_at.to_pydatetime() if hasattr(last_commit_at, 'to_pydatetime') else last_commit_at,
            'collected_at': datetime.now(),
            'last_updated_at': datetime.now(),
            'collection_version': '2.0'
        }

        self.hot.upsert_repository_metrics(metrics)
        logger.info(f"Built repository aggregate: {total_commits} commits, {total_contributors} contributors")

    def _build_daily_aggregates(self, codebase_id: str, commits_df: pd.DataFrame) -> None:
        """Build daily time-series aggregates."""
        logger.debug(f"Building daily aggregates for repo {codebase_id}")

        # Deduplicate commits by SHA
        unique_commits = commits_df.drop_duplicates(subset=['commit_sha'])

        # Group by date
        unique_commits['date'] = unique_commits['committed_at'].dt.date

        daily_df = unique_commits.groupby('date').agg({
            'commit_sha': 'count',
            'additions_lines': 'sum',
            'deletions_lines': 'sum',
            'net_lines': 'sum',
            'churn_lines': 'sum',
            'addition_bytes': 'sum',
            'deletion_bytes': 'sum',
            'net_bytes': 'sum',
            'patch_bytes': 'sum',
            'sloc': 'sum',
            'author_email': 'nunique',
            'files_changed': 'sum'
        }).reset_index()

        daily_df.columns = [
            'date',
            'commits_count',
            'additions_lines',
            'deletions_lines',
            'net_change_lines',
            'churn_lines',
            'addition_bytes',
            'deletion_bytes',
            'net_bytes',
            'patch_bytes',
            'sloc',
            'active_contributors',
            'files_changed'
        ]

        # Calculate cumulative totals
        daily_df = daily_df.sort_values('date')
        daily_df['cumulative_lines'] = daily_df['net_change_lines'].cumsum()
        daily_df['cumulative_sloc'] = daily_df['sloc'].cumsum()

        # Convert to list of dicts
        daily_metrics = daily_df.to_dict('records')

        # Bulk insert
        self.hot.insert_daily_metrics(codebase_id, daily_metrics)
        logger.info(f"Built {len(daily_metrics)} daily aggregates")

    def _build_monthly_aggregates(self, codebase_id: str, commits_df: pd.DataFrame) -> None:
        """Build monthly rollup aggregates."""
        logger.debug(f"Building monthly aggregates for repo {codebase_id}")

        # Deduplicate commits by SHA
        unique_commits = commits_df.drop_duplicates(subset=['commit_sha'])

        # Group by month
        unique_commits['year_month'] = unique_commits['committed_at'].dt.strftime('%Y-%m')

        monthly_df = unique_commits.groupby('year_month').agg({
            'commit_sha': 'count',
            'additions_lines': ['sum', 'max', 'mean'],
            'deletions_lines': 'sum',
            'net_lines': 'sum',
            'addition_bytes': 'sum',
            'deletion_bytes': 'sum',
            'net_bytes': 'sum',
            'sloc': ['sum', 'max', 'mean'],
            'author_email': 'nunique'
        }).reset_index()

        # Flatten multi-level columns
        monthly_df.columns = [
            'year_month',
            'commits_count',
            'additions_lines',
            'max_commit_size_lines',
            'avg_commit_size_lines',
            'deletions_lines',
            'net_lines',
            'addition_bytes',
            'deletion_bytes',
            'net_sloc',
            'sloc_sum',
            'max_commit_size_sloc',
            'avg_commit_size_sloc',
            'unique_contributors'
        ]

        # Drop the extra sloc_sum column (we use net_sloc)
        monthly_df = monthly_df.drop(columns=['sloc_sum'])

        # Convert to list of dicts
        monthly_metrics = monthly_df.to_dict('records')

        # Bulk insert
        self.hot.insert_monthly_metrics(codebase_id, monthly_metrics)
        logger.info(f"Built {len(monthly_metrics)} monthly aggregates")

    def _calculate_branch_metrics(self, codebase_id: str, branch_name: str, branch_df: pd.DataFrame) -> dict:
        """Calculate metrics for a single branch.

        Args:
            codebase_id: Repository ID
            branch_name: Branch name
            branch_df: DataFrame of commits for this branch

        Returns:
            Dictionary of branch metrics
        """
        logger.debug(f"Calculating metrics for branch {branch_name}")

        # Get head commit
        latest_commit = branch_df.loc[branch_df['committed_at'].idxmax()]
        head_commit_sha = latest_commit['commit_sha']

        # Calculate aggregates
        total_commits = len(branch_df)
        unique_contributors = branch_df['author_email'].nunique()

        # Line-based metrics
        current_lines = branch_df['net_lines'].sum()
        total_additions_lines = branch_df['additions_lines'].sum()
        total_deletions_lines = branch_df['deletions_lines'].sum()

        # Byte-based metrics
        current_sloc = branch_df['sloc'].sum()
        total_addition_bytes = branch_df['addition_bytes'].sum()
        total_deletion_bytes = branch_df['deletion_bytes'].sum()

        # Timestamps
        first_commit = branch_df['committed_at'].min()
        last_commit = branch_df['committed_at'].max()

        # Total files
        total_files = branch_df['files_changed'].sum()

        return {
            'codebase_id': codebase_id,
            'branch_name': str(branch_name),
            'head_commit_sha': str(head_commit_sha),
            'divergence_point_sha': None,
            'parent_branch': None,
            'created_at': first_commit.to_pydatetime() if hasattr(first_commit, 'to_pydatetime') else first_commit,
            'last_commit_at': last_commit.to_pydatetime() if hasattr(last_commit, 'to_pydatetime') else last_commit,
            'current_lines': int(current_lines),
            'unique_lines': int(current_lines),
            'total_additions_lines': int(total_additions_lines),
            'total_deletions_lines': int(total_deletions_lines),
            'current_sloc': int(current_sloc),
            'churn_sloc': int(total_addition_bytes + total_deletion_bytes) // 50,
            'unique_sloc': int(current_sloc),
            'total_addition_bytes': int(total_addition_bytes),
            'total_deletion_bytes': int(total_deletion_bytes),
            'total_commits': int(total_commits),
            'unique_commits': int(total_commits),
            'unique_contributors': int(unique_contributors),
            'total_files': int(total_files),
            'is_default_branch': False,
            'is_active': True,
            'is_merged': False,
            'is_deleted': False,
            'merged_at': None,
            'deleted_at': None,
            'last_analyzed_at': datetime.now()
        }

    def _aggregates_exist(self, codebase_id: str) -> bool:
        """Check if aggregates exist for repository.

        Args:
            codebase_id: Repository ID

        Returns:
            True if repository metrics exist
        """
        metrics = self.hot.get_repository_metrics(codebase_id)
        return metrics is not None

