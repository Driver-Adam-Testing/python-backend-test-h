"""DuckDB storage backend for hot aggregates."""

import logging
from pathlib import Path
from typing import Any

import duckdb

from src.schemas.hot_schemas import ALL_HOT_SCHEMAS

logger = logging.getLogger(__name__)


class HotStorage:
    """DuckDB-based storage for hot aggregates.

    Provides fast access to pre-aggregated metrics including repository summaries,
    daily/monthly metrics, branch summaries, and branch state history.

    Usage:
        with HotStorage(path) as hot:
            hot.upsert_repository_metrics(metrics)
            data = hot.get_repository_metrics(codebase_id)
    """

    def __init__(self, storage_path: Path):
        """Initialize hot storage.

        Args:
            storage_path: Path to DuckDB file (e.g., .../hot/summary.duckdb)
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        logger.debug(f"Initialized HotStorage at {self.storage_path}")

    def connect(self):
        """Connect to DuckDB database and initialize schemas.

        Returns:
            Self for chaining
        """
        logger.info(f"Connecting to DuckDB at {self.storage_path}")
        self.conn = duckdb.connect(str(self.storage_path))

        # Create all tables
        for ddl in ALL_HOT_SCHEMAS:
            try:
                self.conn.execute(ddl)
            except Exception as e:
                logger.error(f"Failed to execute DDL: {e}")
                raise

        logger.info("Successfully initialized all hot storage tables")
        return self

    def close(self):
        """Close database connection."""
        if self.conn:
            logger.debug("Closing DuckDB connection")
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    # Repository Metrics
    def upsert_repository_metrics(self, metrics: dict) -> None:
        """Insert or update repository metrics.

        Args:
            metrics: Dictionary with all repository metric fields
        """
        logger.debug(f"Upserting repository metrics for codebase {metrics.get('codebase_id')}")

        # Build dynamic SQL based on provided fields
        columns = list(metrics.keys())
        placeholders = ["?" for _ in columns]
        update_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns if col != "codebase_id"])

        sql = f"""
            INSERT INTO repository_metrics ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT (codebase_id)
            DO UPDATE SET {update_clause}
        """

        try:
            self.conn.execute(sql, list(metrics.values()))
            logger.info(f"Successfully upserted repository metrics for codebase {metrics.get('codebase_id')}")
        except Exception as e:
            logger.error(f"Failed to upsert repository metrics: {e}")
            raise

    def get_repository_metrics(self, codebase_id: str) -> dict | None:
        """Get repository metrics.

        Args:
            codebase_id: Codebase UUID identifier

        Returns:
            Dictionary of metrics or None if not found
        """
        logger.debug(f"Fetching repository metrics for codebase {codebase_id}")

        result = self.conn.execute(
            "SELECT * FROM repository_metrics WHERE codebase_id = ?",
            [codebase_id]
        ).fetchone()

        if result:
            columns = self._get_column_names('repository_metrics')
            return dict(zip(columns, result))

        logger.debug(f"No metrics found for codebase {codebase_id}")
        return None

    # Daily Metrics
    def insert_daily_metrics(self, codebase_id: str, metrics: list[dict]) -> None:
        """Batch insert daily metrics.

        Args:
            codebase_id: Codebase UUID identifier
            metrics: List of daily metric dictionaries
        """
        if not metrics:
            logger.debug("No daily metrics to insert")
            return

        logger.info(f"Inserting {len(metrics)} daily metrics for codebase {codebase_id}")

        # Prepare data for executemany
        rows = []
        for m in metrics:
            row = [codebase_id]
            row.extend([
                m.get('date'),
                m.get('additions_lines', 0),
                m.get('deletions_lines', 0),
                m.get('net_change_lines', 0),
                m.get('churn_lines', 0),
                m.get('cumulative_lines', 0),
                m.get('addition_bytes', 0),
                m.get('deletion_bytes', 0),
                m.get('net_bytes', 0),
                m.get('patch_bytes', 0),
                m.get('cumulative_sloc', 0),
                m.get('commits_count', 0),
                m.get('active_contributors', 0),
                m.get('files_changed', 0),
            ])
            rows.append(row)

        try:
            self.conn.executemany("""
                INSERT INTO daily_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (codebase_id, date) DO NOTHING
            """, rows)
            logger.info(f"Successfully inserted daily metrics for codebase {codebase_id}")
        except Exception as e:
            logger.error(f"Failed to insert daily metrics: {e}")
            raise

    def get_daily_metrics(
        self, codebase_id: str, start_date: str = None, end_date: str = None
    ) -> list[dict]:
        """Get daily metrics for a date range.

        Args:
            codebase_id: Codebase UUID identifier
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            List of daily metric dictionaries
        """
        query = "SELECT * FROM daily_metrics WHERE codebase_id = ?"
        params = [codebase_id]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date"

        logger.debug(f"Fetching daily metrics for codebase {codebase_id} (range: {start_date} to {end_date})")

        result = self.conn.execute(query, params).fetchall()
        columns = self._get_column_names('daily_metrics')
        return [dict(zip(columns, row)) for row in result]

    # Monthly Metrics
    def insert_monthly_metrics(self, codebase_id: str, metrics: list[dict]) -> None:
        """Batch insert monthly metrics.

        Args:
            codebase_id: Codebase UUID identifier
            metrics: List of monthly metric dictionaries
        """
        if not metrics:
            logger.debug("No monthly metrics to insert")
            return

        logger.info(f"Inserting {len(metrics)} monthly metrics for codebase {codebase_id}")

        rows = []
        for m in metrics:
            row = [
                codebase_id,
                m.get('year_month'),
                m.get('commits_count', 0),
                m.get('unique_contributors', 0),
                m.get('additions_lines', 0),
                m.get('deletions_lines', 0),
                m.get('net_lines', 0),
                m.get('addition_bytes', 0),
                m.get('deletion_bytes', 0),
                m.get('net_sloc', 0),
                m.get('avg_commit_size_lines'),
                m.get('avg_commit_size_sloc'),
                m.get('max_commit_size_lines'),
                m.get('max_commit_size_sloc'),
            ]
            rows.append(row)

        try:
            self.conn.executemany("""
                INSERT INTO monthly_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (codebase_id, year_month) DO NOTHING
            """, rows)
            logger.info(f"Successfully inserted monthly metrics for codebase {codebase_id}")
        except Exception as e:
            logger.error(f"Failed to insert monthly metrics: {e}")
            raise

    def get_monthly_metrics(self, codebase_id: str) -> list[dict]:
        """Get monthly metrics for a repository.

        Args:
            codebase_id: Codebase UUID identifier

        Returns:
            List of monthly metric dictionaries
        """
        logger.debug(f"Fetching monthly metrics for codebase {codebase_id}")

        result = self.conn.execute("""
            SELECT * FROM monthly_metrics
            WHERE codebase_id = ?
            ORDER BY year_month
        """, [codebase_id]).fetchall()

        columns = self._get_column_names('monthly_metrics')
        return [dict(zip(columns, row)) for row in result]

    # Branch Metrics
    def upsert_branch_metrics(self, metrics: dict) -> None:
        """Insert or update branch metrics.

        Args:
            metrics: Dictionary with all branch metric fields
        """
        logger.debug(f"Upserting branch metrics for branch {metrics.get('branch_name')} in codebase {metrics.get('codebase_id')}")

        # Build dynamic SQL based on provided fields
        columns = list(metrics.keys())
        placeholders = ["?" for _ in columns]
        update_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ('codebase_id', 'branch_name')])

        sql = f"""
            INSERT INTO branch_metrics ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT (codebase_id, branch_name)
            DO UPDATE SET {update_clause}
        """

        try:
            self.conn.execute(sql, list(metrics.values()))
            logger.info(f"Successfully upserted branch metrics for branch {metrics.get('branch_name')}")
        except Exception as e:
            logger.error(f"Failed to upsert branch metrics: {e}")
            raise

    def get_branch_metrics(self, codebase_id: str, branch_name: str) -> dict | None:
        """Get metrics for a specific branch.

        Args:
            codebase_id: Codebase UUID identifier
            branch_name: Branch name

        Returns:
            Branch metrics dictionary or None if not found
        """
        logger.debug(f"Fetching branch metrics for {branch_name} in codebase {codebase_id}")

        try:
            cursor = self.conn.execute("""
                SELECT * FROM branch_metrics
                WHERE codebase_id = ? AND branch_name = ?
            """, [codebase_id, branch_name])

            result = cursor.fetchone()

            if result:
                # Get column names from cursor description
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, result))

            logger.debug(f"No metrics found for branch {branch_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to get branch metrics: {e}")
            return None

    def get_all_branch_metrics(self, codebase_id: str) -> list[dict]:
        """Get metrics for all branches in a repository.

        Args:
            codebase_id: Codebase UUID identifier

        Returns:
            List of branch metrics dictionaries
        """
        logger.debug(f"Fetching all branch metrics for codebase {codebase_id}")

        try:
            cursor = self.conn.execute("""
                SELECT * FROM branch_metrics
                WHERE codebase_id = ?
                ORDER BY last_commit_at DESC
            """, [codebase_id])

            result = cursor.fetchall()

            # Get column names from cursor description
            columns = [desc[0] for desc in cursor.description]
            branches = [dict(zip(columns, row)) for row in result]
            logger.info(f"Found {len(branches)} branches for codebase {codebase_id}")
            return branches
        except Exception as e:
            logger.error(f"Failed to get branch metrics: {e}")
            return []

    def delete_branch_metrics(self, codebase_id: str, branch_name: str) -> None:
        """Delete branch metrics (used for rebase recalculation).

        Args:
            codebase_id: Codebase UUID identifier
            branch_name: Branch name to delete
        """
        logger.debug(f"Deleting metrics for branch {branch_name} in codebase {codebase_id}")

        try:
            self.conn.execute("""
                DELETE FROM branch_metrics
                WHERE codebase_id = ? AND branch_name = ?
            """, [codebase_id, branch_name])

            logger.info(f"Deleted metrics for branch {branch_name}")
        except Exception as e:
            logger.error(f"Failed to delete branch metrics: {e}")
            raise

    # Helper methods
    def _get_column_names(self, table_name: str) -> list[str]:
        """Get column names for a table.

        Args:
            table_name: Name of the table

        Returns:
            List of column names
        """
        result = self.conn.execute(
            f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}' ORDER BY ordinal_position"
        ).fetchall()
        return [row[0] for row in result]

    def execute_query(self, query: str, params: list = None) -> list[dict]:
        """Execute arbitrary SQL query.

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            List of result dictionaries
        """
        logger.debug(f"Executing custom query: {query[:100]}...")

        try:
            cursor = self.conn.execute(query, params or [])
            result = cursor.fetchall()
            if result:
                # Get column names from description
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in result]
            return []
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def vacuum(self) -> None:
        """Optimize database by running VACUUM."""
        logger.info("Running VACUUM to optimize database")
        try:
            self.conn.execute("VACUUM")
            logger.info("VACUUM completed successfully")
        except Exception as e:
            logger.error(f"VACUUM failed: {e}")
            raise

