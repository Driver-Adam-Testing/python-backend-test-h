"""Driver-specific JSON export for analytics integration."""
import time
from datetime import datetime, timezone
from pathlib import Path

from src.storage.hot_storage import HotStorage
from src.storage.parquet_storage import ParquetStorage
from .schemas import (
    OverviewJSON, BranchesJSON, ActivityJSON, OwnershipJSON,
    MetadataJSON, BranchEntry, ActivityEntry,
    DirectoryOwnership, ContributorEntry,
)


class DriverJSONExporter:
    """Export analytics as JSON files for Driver integration.

    Creates separate JSON files matching Driver's API structure:
    - overview.json
    - branches.json
    - activity.json
    - ownership.json  (code ownership by directory, includes contributor data)
    - metadata.json

    Note: No separate contributors.json - contributor data is embedded in ownership.json
    """

    def __init__(
        self,
        codebase_id: str,
        hot_storage: HotStorage,
        warm_storage: ParquetStorage | None = None,
        cold_storage: ParquetStorage | None = None,
        output_dir: Path | None = None,
    ):
        self.codebase_id = codebase_id
        self.hot = hot_storage
        self.warm_storage = warm_storage
        self.cold_storage = cold_storage
        self.output_dir = output_dir or Path(".")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self) -> list[Path]:
        """Export all JSON files for this codebase."""
        start = time.time()

        files = [
            self._export_overview(),
            self._export_branches(),
            self._export_activity(),
            self._export_ownership(),  # Code ownership + contributor data
        ]

        files.append(self._export_metadata(time.time() - start))
        return [f for f in files if f]

    def _export_overview(self) -> Path | None:
        """Export overview.json using existing HotStorage patterns."""
        metrics = self.hot.get_repository_metrics(self.codebase_id)
        if not metrics:
            return None

        # Extract owner from full_name (format: "owner/repo")
        full_name = metrics.get('full_name', '')
        owner = full_name.split('/')[0] if '/' in full_name else ''

        # Extract metrics from hot storage
        total_addition_bytes = metrics.get('total_addition_bytes', 0)
        total_deletion_bytes = metrics.get('total_deletion_bytes', 0)
        # Compute net_sloc the same way GitStats backend does: (addition_bytes - deletion_bytes) / 50
        net_sloc = (total_addition_bytes - total_deletion_bytes) // 50
        total_sloc = metrics.get('total_sloc', 0)
        total_lines = metrics.get('total_lines', net_sloc)

        overview = OverviewJSON(
            codebase_id=self.codebase_id,
            display_name=metrics.get('repository_name', self.codebase_id),
            repository_name=metrics.get('repository_name', self.codebase_id),
            full_name=full_name,
            owner=owner,
            total_commits=metrics.get('total_commits', 0),
            total_contributors=metrics.get('total_contributors', 0),
            total_branches=metrics.get('total_branches', 0),
            # Line-based metrics
            total_lines=total_lines,
            total_additions_lines=metrics.get('total_additions_lines', 0),
            total_deletions_lines=metrics.get('total_deletions_lines', 0),
            total_churn=metrics.get('total_additions_lines', 0) + metrics.get('total_deletions_lines', 0),
            # Byte-based SLOC metrics
            total_sloc=total_sloc,  # Churn-based SLOC (stored in hot storage)
            net_sloc=net_sloc,  # Net SLOC: (addition_bytes - deletion_bytes) / 50
            current_sloc=net_sloc,  # Alias for net_sloc (current codebase size)
            total_addition_bytes=total_addition_bytes,
            total_deletion_bytes=total_deletion_bytes,
            avg_bytes_per_line=metrics.get('avg_bytes_per_line'),
            total_files=metrics.get('total_files', 0),
            # Branch and language info
            default_branch=metrics.get('default_branch', 'main'),
            primary_language=metrics.get('primary_language'),
            # Timestamps
            first_commit_date=metrics.get('first_commit_at'),
            last_commit_date=metrics.get('last_commit_at'),
            collected_at=metrics.get('collected_at') or datetime.now(timezone.utc),
            last_updated_at=metrics.get('last_updated_at') or datetime.now(timezone.utc),
        )

        return self._write('overview.json', overview)

    def _export_branches(self) -> Path | None:
        """Export branches.json using existing HotStorage patterns."""
        branches = self.hot.get_all_branch_metrics(self.codebase_id)
        if not branches:
            return None

        data = BranchesJSON(
            codebase_id=self.codebase_id,
            branches=[
                BranchEntry(
                    name=b.get('branch_name'),
                    is_default=b.get('is_default_branch', False),
                    commits=b.get('total_commits', 0),
                    last_commit_date=b.get('last_commit_at'),
                    last_analyzed_at=b.get('last_analyzed_at') or datetime.now(timezone.utc),
                    status='active' if b.get('is_active') else 'stale',
                    # Branch metadata
                    head_commit_sha=b.get('head_commit_sha', ''),
                    divergence_point_sha=b.get('divergence_point_sha'),
                    parent_branch=b.get('parent_branch'),
                    created_at=b.get('created_at'),
                    # Line-based metrics
                    current_lines=b.get('current_lines', 0),
                    unique_lines=b.get('unique_lines', 0),
                    total_additions_lines=b.get('total_additions_lines', 0),
                    total_deletions_lines=b.get('total_deletions_lines', 0),
                    # Byte-based SLOC metrics
                    current_sloc=b.get('current_sloc', 0),
                    churn_sloc=b.get('churn_sloc', 0),
                    unique_sloc=b.get('unique_sloc', 0),
                    total_addition_bytes=b.get('total_addition_bytes', 0),
                    total_deletion_bytes=b.get('total_deletion_bytes', 0),
                    # Branch stats
                    unique_commits=b.get('unique_commits', 0),
                    unique_contributors=b.get('unique_contributors', 0),
                    total_files=b.get('total_files', 0),
                    # Branch state flags
                    is_active=b.get('is_active', True),
                    is_merged=b.get('is_merged', False),
                    is_deleted=b.get('is_deleted', False),
                    merged_at=b.get('merged_at'),
                    deleted_at=b.get('deleted_at'),
                )
                for b in branches
            ]
        )

        return self._write('branches.json', data)

    def _export_activity(self) -> Path | None:
        """Export activity.json using existing HotStorage patterns."""
        # Last 365 days of daily metrics
        metrics = self.hot.get_daily_metrics(self.codebase_id)
        if not metrics:
            return None

        data = ActivityJSON(
            codebase_id=self.codebase_id,
            daily_activity=[
                ActivityEntry(
                    date=str(m.get('date')),
                    commits=m.get('commits_count', 0),
                    # Line-based metrics
                    additions=m.get('additions_lines', 0),
                    deletions=m.get('deletions_lines', 0),
                    active_contributors=m.get('active_contributors', 0),
                    files_changed=m.get('files_changed', 0),
                    cumulative_lines=m.get('cumulative_lines', 0),
                    # Byte-based metrics for SLOC calculation
                    addition_bytes=m.get('addition_bytes', 0),
                    deletion_bytes=m.get('deletion_bytes', 0),
                    net_bytes=m.get('net_bytes', 0),
                    patch_bytes=m.get('patch_bytes', 0),
                    cumulative_sloc=m.get('cumulative_sloc', 0),
                )
                for m in metrics[-365:]  # Last year
            ]
        )

        return self._write('activity.json', data)

    def _export_ownership(self) -> Path | None:
        """Export ownership.json with code ownership by directory.

        This includes contributor data - the same data used by both the
        CodeOwnershipMap and ContributorStatsTable components.
        """
        if not self.warm_storage or not self.cold_storage:
            return None

        import pandas as pd

        # Get file changes from cold storage
        file_changes_df = self.cold_storage.read_file_changes(self.codebase_id)
        if file_changes_df is None or len(file_changes_df) == 0:
            return None

        # Get commits from warm storage
        commits_df = self.warm_storage.read_commits(self.codebase_id)
        if commits_df is None or len(commits_df) == 0:
            return None

        commits_df = commits_df.drop_duplicates(subset=["commit_sha"], keep="first")

        # Join and compute ownership
        joined = file_changes_df.merge(commits_df, on="commit_sha", how="inner")
        if joined.empty:
            return None

        # Extract directory (first two path components)
        def extract_directory(path: str) -> str:
            if not path or pd.isna(path):
                return "root"
            parts = path.split("/")
            if len(parts) <= 1:
                return "root"
            elif len(parts) == 2:
                return parts[0]
            else:
                return "/".join(parts[:2])

        joined["directory"] = joined["file_path"].apply(extract_directory)

        # Calculate SLOC estimate from bytes
        add_col = "addition_bytes_x" if "addition_bytes_x" in joined.columns else "addition_bytes"
        del_col = "deletion_bytes_x" if "deletion_bytes_x" in joined.columns else "deletion_bytes"

        joined["sloc"] = (
            joined[add_col].fillna(0) + joined[del_col].fillna(0)
        ) / 50
        joined["sloc"] = joined["sloc"].astype(int)

        # Aggregate by directory and contributor
        ownership = (
            joined.groupby(["directory", "author_email", "author_name"])
            .agg({
                "sloc": "sum",
                "commit_sha": "nunique",
                "committed_at": ["min", "max", "nunique"],
            })
            .reset_index()
        )
        ownership.columns = [
            "directory", "author_email", "author_name", "sloc", "commits",
            "first_commit_at", "last_commit_at", "active_days"
        ]

        # Calculate totals and ownership percentages
        dir_totals = ownership.groupby("directory")["sloc"].sum()
        ownership["ownership_pct"] = (
            ownership["sloc"] / ownership["directory"].map(dir_totals) * 100
        ).fillna(0.0)

        contributor_counts = ownership.groupby("directory")["author_email"].nunique()
        ownership = ownership.sort_values(["directory", "sloc"], ascending=[True, False])

        # Build result
        directories = []
        for directory in ownership["directory"].unique():
            dir_data = ownership[ownership["directory"] == directory]
            total_sloc = int(dir_totals[directory])
            total_contributors = int(contributor_counts[directory])

            top_contributors = dir_data.head(10)  # Max 10 per directory
            if len(top_contributors) == 0:
                continue

            primary = top_contributors.iloc[0]

            contributors = [
                ContributorEntry(
                    contributor_email=str(c["author_email"]),
                    contributor_name=str(c["author_name"]),
                    total_commits=int(c["commits"]),
                    total_sloc=int(c["sloc"]),
                    ownership_percentage=float(c["ownership_pct"]),
                    first_commit_at=c["first_commit_at"],
                    last_commit_at=c["last_commit_at"],
                    active_days=int(c["active_days"]),
                )
                for _, c in top_contributors.iterrows()
            ]

            directories.append(DirectoryOwnership(
                directory_path=str(directory),
                total_commits=int(dir_data["commits"].sum()),
                total_sloc=total_sloc,
                unique_contributors=total_contributors,
                primary_owner_email=str(primary["author_email"]),
                primary_owner_name=str(primary["author_name"]),
                primary_owner_percentage=float(primary["ownership_pct"]),
                contributors=contributors,
            ))

        # Sort by total SLOC descending
        directories.sort(key=lambda x: x.total_sloc, reverse=True)

        data = OwnershipJSON(
            codebase_id=self.codebase_id,
            directories=directories,
        )

        return self._write('ownership.json', data)

    def _export_metadata(self, duration: float) -> Path:
        """Export metadata.json with generation info."""
        data = MetadataJSON(
            codebase_id=self.codebase_id,
            generated_at=datetime.now(timezone.utc),
            status='complete',
            generation_seconds=duration,
        )

        return self._write('metadata.json', data)

    def _write(self, filename: str, data) -> Path:
        """Write Pydantic model to JSON file."""
        path = self.output_dir / filename
        path.write_text(data.model_dump_json(indent=2))
        return path

