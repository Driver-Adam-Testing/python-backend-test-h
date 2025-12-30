"""Unit tests for storage modules."""
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from analytics.storage.hot_storage import HotStorage
from analytics.storage.parquet_storage import ParquetStorage


class TestHotStorage:
    """Tests for HotStorage class."""

    @pytest.fixture
    def hot_storage(self, tmp_path):
        """Create a temporary hot storage."""
        storage = HotStorage(tmp_path / "hot" / "test.duckdb")
        storage.connect()
        yield storage
        storage.close()

    def test_connect_creates_tables(self, hot_storage):
        """Test that connect creates all required tables."""
        # Query for tables
        result = hot_storage.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        
        table_names = [r[0] for r in result]
        
        assert "repository_metrics" in table_names
        assert "daily_metrics" in table_names
        assert "monthly_metrics" in table_names
        assert "branch_metrics" in table_names

    def test_upsert_repository_metrics(self, hot_storage):
        """Test upserting repository metrics."""
        metrics = {
            "codebase_id": "test-uuid-123",
            "repository_name": "test-repo",
            "full_name": "owner/test-repo",
            "owner": "owner",
            "total_commits": 100,
            "total_contributors": 5,
            "total_branches": 3,
            "total_files": 50,
            "total_lines": 1000,
            "total_additions_lines": 1500,
            "total_deletions_lines": 500,
            "total_sloc": 1000,
            "current_sloc": 1000,
            "total_addition_bytes": 75000,
            "total_deletion_bytes": 25000,
            "avg_bytes_per_line": 50.0,
            "default_branch": "main",
            "primary_language": "Python",
            "first_commit_at": datetime.now(timezone.utc),
            "last_commit_at": datetime.now(timezone.utc),
            "collected_at": datetime.now(timezone.utc),
            "last_updated_at": datetime.now(timezone.utc),
            "collection_version": "2.0",
        }
        
        hot_storage.upsert_repository_metrics(metrics)
        
        result = hot_storage.get_repository_metrics("test-uuid-123")
        
        assert result is not None
        assert result["repository_name"] == "test-repo"
        assert result["total_commits"] == 100

    def test_get_repository_metrics_not_found(self, hot_storage):
        """Test getting non-existent repository metrics."""
        result = hot_storage.get_repository_metrics("non-existent")
        
        assert result is None

    def test_insert_daily_metrics(self, hot_storage):
        """Test inserting daily metrics."""
        from datetime import date
        
        metrics = [
            {
                "date": date(2024, 1, 1),
                "additions_lines": 100,
                "deletions_lines": 50,
                "net_change_lines": 50,
                "churn_lines": 150,
                "cumulative_lines": 50,
                "addition_bytes": 5000,
                "deletion_bytes": 2500,
                "net_bytes": 2500,
                "patch_bytes": 7500,
                "cumulative_sloc": 150,
                "commits_count": 10,
                "active_contributors": 3,
                "files_changed": 15,
            },
            {
                "date": date(2024, 1, 2),
                "additions_lines": 80,
                "deletions_lines": 30,
                "net_change_lines": 50,
                "churn_lines": 110,
                "cumulative_lines": 100,
                "addition_bytes": 4000,
                "deletion_bytes": 1500,
                "net_bytes": 2500,
                "patch_bytes": 5500,
                "cumulative_sloc": 260,
                "commits_count": 8,
                "active_contributors": 2,
                "files_changed": 10,
            },
        ]
        
        hot_storage.insert_daily_metrics("test-uuid", metrics)
        
        result = hot_storage.get_daily_metrics("test-uuid")
        
        assert len(result) == 2
        assert result[0]["commits_count"] == 10

    def test_upsert_branch_metrics(self, hot_storage):
        """Test upserting branch metrics."""
        metrics = {
            "codebase_id": "test-uuid",
            "branch_name": "main",
            "head_commit_sha": "abc123",
            "divergence_point_sha": None,
            "parent_branch": None,
            "created_at": None,
            "last_commit_at": datetime.now(timezone.utc),
            "current_lines": 1000,
            "unique_lines": 1000,
            "total_additions_lines": 1500,
            "total_deletions_lines": 500,
            "current_sloc": 1000,
            "churn_sloc": 2000,
            "unique_sloc": 1000,
            "total_addition_bytes": 75000,
            "total_deletion_bytes": 25000,
            "total_commits": 100,
            "unique_commits": 100,
            "unique_contributors": 5,
            "total_files": 50,
            "is_default_branch": True,
            "is_active": True,
            "is_merged": False,
            "is_deleted": False,
            "merged_at": None,
            "deleted_at": None,
            "last_analyzed_at": datetime.now(timezone.utc),
        }
        
        hot_storage.upsert_branch_metrics(metrics)
        
        result = hot_storage.get_branch_metrics("test-uuid", "main")
        
        assert result is not None
        assert result["total_commits"] == 100


class TestParquetStorage:
    """Tests for ParquetStorage class."""

    @pytest.fixture
    def parquet_storage(self, tmp_path):
        """Create a temporary parquet storage."""
        return ParquetStorage(tmp_path / "parquet")

    def test_write_and_read_commits(self, parquet_storage):
        """Test writing and reading commits."""
        from datetime import date
        
        commits = [
            {
                "commit_sha": "abc123",
                "codebase_id": "test-uuid",
                "branch_name": "main",
                "committed_at": datetime.now(timezone.utc),
                "collected_at": datetime.now(timezone.utc),
                "commit_date": date.today(),
                "commit_year": 2024,
                "commit_month": 1,
                "commit_day": 15,
                "author_email": "dev@example.com",
                "author_name": "Dev",
                "committer_email": "dev@example.com",
                "committer_name": "Dev",
                "message": "Test commit",
                "message_length": 11,
                "parent_count": 1,
                "is_merge_commit": False,
                "files_changed": 5,
                "additions_lines": 100,
                "deletions_lines": 50,
                "net_lines": 50,
                "churn_lines": 150,
                "addition_bytes": 5000,
                "deletion_bytes": 2500,
                "patch_bytes": 7500,
                "net_bytes": 2500,
                "sloc": 150,
                "bytes_per_line": 50.0,
                "commit_size_category": "medium",
                "is_refactor": False,
                "collection_version": "2.0",
            }
        ]
        
        parquet_storage.write_commits("test-uuid", commits)
        
        result = parquet_storage.read_commits("test-uuid")
        
        assert len(result) == 1
        assert result.iloc[0]["commit_sha"] == "abc123"

    def test_read_commits_not_found(self, parquet_storage):
        """Test reading commits for non-existent repo."""
        result = parquet_storage.read_commits("non-existent")
        
        assert len(result) == 0

    def test_exists(self, parquet_storage):
        """Test checking file existence."""
        from datetime import date
        
        assert not parquet_storage.exists("warm", "commits", "test-uuid")
        
        # Write some data
        commits = [{
            "commit_sha": "abc123",
            "codebase_id": "test-uuid",
            "branch_name": "main",
            "committed_at": datetime.now(timezone.utc),
            "collected_at": datetime.now(timezone.utc),
            "commit_date": date.today(),
            "commit_year": 2024,
            "commit_month": 1,
            "commit_day": 15,
            "author_email": "dev@example.com",
            "author_name": "Dev",
            "committer_email": "dev@example.com",
            "committer_name": "Dev",
            "message": "Test",
            "message_length": 4,
            "parent_count": 0,
            "is_merge_commit": False,
            "files_changed": 1,
            "additions_lines": 10,
            "deletions_lines": 0,
            "net_lines": 10,
            "churn_lines": 10,
            "addition_bytes": 500,
            "deletion_bytes": 0,
            "patch_bytes": 500,
            "net_bytes": 500,
            "sloc": 10,
            "bytes_per_line": 50.0,
            "commit_size_category": "small",
            "is_refactor": False,
            "collection_version": "2.0",
        }]
        
        parquet_storage.write_commits("test-uuid", commits)
        
        assert parquet_storage.exists("warm", "commits", "test-uuid")

