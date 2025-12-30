"""
Analytics Pipeline Orchestrator.

Coordinates all phases of the analytics pipeline:
1. Clone repository
2. Extract commits
3. Discover branches
4. Build aggregates
5. Calculate ownership
6. Export to JSON
7. Upload to S3
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import pygit2
from pydantic import BaseModel

from src.storage.hot_storage import HotStorage
from src.storage.parquet_storage import ParquetStorage
from src.aggregation.engine import AggregationEngine
from src.export.exporter import DriverJSONExporter

from .phases.clone import clone_repository, open_repository, cleanup_repository, CloneResult
from .phases.extract import extract_commits, ExtractResult
from .phases.branches import discover_branches, BranchesResult

logger = logging.getLogger(__name__)


class PipelineConfig(BaseModel):
    """Configuration for analytics pipeline."""
    work_dir: Path = Path("/tmp/analytics")
    cleanup_on_complete: bool = True
    default_branch_only: bool = False
    include_patches: bool = True


class PipelineInput(BaseModel):
    """Input for analytics pipeline."""
    codebase_id: str
    organization_id: str
    clone_url: str
    repo_owner: str
    repo_name: str
    auth_token: str | None = None


class PipelineOutput(BaseModel):
    """Output from analytics pipeline."""
    success: bool
    codebase_id: str
    total_commits: int = 0
    total_branches: int = 0
    total_contributors: int = 0
    json_files: list[str] = []
    error: str | None = None
    duration_seconds: float = 0.0


@dataclass
class PipelineContext:
    """Internal context for pipeline execution."""
    config: PipelineConfig
    input: PipelineInput

    # Storage
    hot_storage: HotStorage | None = None
    warm_storage: ParquetStorage | None = None
    cold_storage: ParquetStorage | None = None

    # Repository state
    repo_path: Path | None = None
    repo: pygit2.Repository | None = None

    # Results from phases
    clone_result: CloneResult | None = None
    extract_result: ExtractResult | None = None
    branches_result: BranchesResult | None = None

    # Timing
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AnalyticsPipeline:
    """
    Main analytics pipeline orchestrator.

    Coordinates all phases and manages resources.

    Example:
        >>> config = PipelineConfig(work_dir=Path("/tmp/analytics"))
        >>> pipeline = AnalyticsPipeline(config)
        >>> result = pipeline.run(PipelineInput(
        ...     codebase_id="uuid",
        ...     organization_id="org-uuid",
        ...     clone_url="https://github.com/owner/repo",
        ...     repo_owner="owner",
        ...     repo_name="repo"
        ... ))
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.config.work_dir.mkdir(parents=True, exist_ok=True)

    def run(self, input: PipelineInput) -> PipelineOutput:
        """
        Execute the full analytics pipeline.

        Args:
            input: Pipeline input with repository details

        Returns:
            PipelineOutput with results
        """
        logger.info(f"Starting analytics pipeline for {input.codebase_id}")

        ctx = PipelineContext(config=self.config, input=input)

        try:
            # Initialize storage
            self._init_storage(ctx)

            # Phase 1: Clone
            self._phase_clone(ctx)

            # Phase 2: Extract commits
            self._phase_extract(ctx)

            # Phase 3: Discover branches
            self._phase_branches(ctx)

            # Phase 4: Store in warm/cold storage
            self._phase_store(ctx)

            # Phase 5: Build aggregates
            self._phase_aggregate(ctx)

            # Phase 6: Export to JSON
            json_files = self._phase_export(ctx)

            # Calculate duration
            duration = (datetime.now(timezone.utc) - ctx.start_time).total_seconds()

            logger.info(f"Pipeline completed successfully for {input.codebase_id}")

            return PipelineOutput(
                success=True,
                codebase_id=input.codebase_id,
                total_commits=ctx.extract_result.total_commits if ctx.extract_result else 0,
                total_branches=len(ctx.branches_result.branches) if ctx.branches_result else 0,
                total_contributors=self._count_contributors(ctx),
                json_files=[str(f) for f in json_files],
                duration_seconds=duration
            )

        except Exception as e:
            logger.error(f"Pipeline failed for {input.codebase_id}: {e}")
            duration = (datetime.now(timezone.utc) - ctx.start_time).total_seconds()

            return PipelineOutput(
                success=False,
                codebase_id=input.codebase_id,
                error=str(e),
                duration_seconds=duration
            )

        finally:
            # Cleanup
            self._cleanup(ctx)

    def _init_storage(self, ctx: PipelineContext) -> None:
        """Initialize storage backends."""
        logger.info("Initializing storage...")

        storage_path = ctx.config.work_dir / ctx.input.codebase_id

        # Hot storage (DuckDB)
        hot_path = storage_path / "hot" / "analytics.duckdb"
        ctx.hot_storage = HotStorage(hot_path)
        ctx.hot_storage.connect()

        # Warm storage (Parquet)
        warm_path = storage_path / "warm"
        ctx.warm_storage = ParquetStorage(warm_path)

        # Cold storage (Parquet)
        cold_path = storage_path / "cold"
        ctx.cold_storage = ParquetStorage(cold_path)

        logger.info("Storage initialized")

    def _phase_clone(self, ctx: PipelineContext) -> None:
        """Phase 1: Clone repository."""
        logger.info("Phase 1: Cloning repository...")

        repo_path = ctx.config.work_dir / ctx.input.codebase_id / "repo"

        result = clone_repository(
            clone_url=ctx.input.clone_url,
            target_path=repo_path,
            auth_token=ctx.input.auth_token,
            clean_existing=True
        )

        if not result.success:
            raise RuntimeError(f"Clone failed: {result.error}")

        ctx.clone_result = result
        ctx.repo_path = result.repo_path
        ctx.repo = result.repo

        logger.info(f"Clone complete: {ctx.repo_path}")

    def _phase_extract(self, ctx: PipelineContext) -> None:
        """Phase 2: Extract commits."""
        logger.info("Phase 2: Extracting commits...")

        if not ctx.repo:
            raise RuntimeError("No repository available for extraction")

        # Determine branches to extract
        branch_names = None  # All branches
        if ctx.config.default_branch_only:
            # Just extract default branch
            branch_names = [ctx.repo.head.shorthand] if not ctx.repo.head_is_unborn else ["main"]

        result = extract_commits(
            repo=ctx.repo,
            codebase_id=ctx.input.codebase_id,
            branch_names=branch_names,
            include_patches=ctx.config.include_patches
        )

        if not result.success:
            raise RuntimeError(f"Extract failed: {result.error}")

        ctx.extract_result = result

        logger.info(f"Extracted {result.total_commits} unique commits ({len(result.commits)} records)")

    def _phase_branches(self, ctx: PipelineContext) -> None:
        """Phase 3: Discover branches."""
        logger.info("Phase 3: Discovering branches...")

        if not ctx.repo:
            raise RuntimeError("No repository available for branch discovery")

        result = discover_branches(
            repo=ctx.repo,
            default_branch_only=ctx.config.default_branch_only
        )

        if not result.success:
            raise RuntimeError(f"Branch discovery failed: {result.error}")

        ctx.branches_result = result

        logger.info(f"Discovered {len(result.branches)} branches (default: {result.default_branch})")

    def _phase_store(self, ctx: PipelineContext) -> None:
        """Phase 4: Store data in warm/cold storage."""
        logger.info("Phase 4: Storing data...")

        if not ctx.extract_result or not ctx.warm_storage:
            return

        # Store commits in warm storage
        commits = ctx.extract_result.commits
        if commits:
            ctx.warm_storage.write_commits(ctx.input.codebase_id, commits)
            logger.info(f"Stored {len(commits)} commit records in warm storage")

        # TODO: Store file changes in cold storage

        logger.info("Data storage complete")

    def _phase_aggregate(self, ctx: PipelineContext) -> None:
        """Phase 5: Build aggregates."""
        logger.info("Phase 5: Building aggregates...")

        if not ctx.hot_storage or not ctx.warm_storage:
            return

        engine = AggregationEngine(ctx.hot_storage, ctx.warm_storage, ctx.cold_storage)

        # Build all aggregates
        engine.build_all_aggregates(ctx.input.codebase_id, force_rebuild=True)

        # Refresh branch metrics
        engine.refresh_branch_metrics(ctx.input.codebase_id)

        logger.info("Aggregates built")

    def _phase_export(self, ctx: PipelineContext) -> list[Path]:
        """Phase 6: Export to JSON."""
        logger.info("Phase 6: Exporting to JSON...")

        if not ctx.hot_storage:
            return []

        output_dir = ctx.config.work_dir / ctx.input.codebase_id / "json"

        exporter = DriverJSONExporter(
            codebase_id=ctx.input.codebase_id,
            hot_storage=ctx.hot_storage,
            warm_storage=ctx.warm_storage,
            cold_storage=ctx.cold_storage,
            output_dir=output_dir
        )

        json_files = exporter.export_all()

        logger.info(f"Exported {len(json_files)} JSON files to {output_dir}")
        return json_files

    def _count_contributors(self, ctx: PipelineContext) -> int:
        """Count unique contributors from extracted commits."""
        if not ctx.extract_result:
            return 0

        emails = set()
        for commit in ctx.extract_result.commits:
            if commit.get('author_email'):
                emails.add(commit['author_email'])

        return len(emails)

    def _cleanup(self, ctx: PipelineContext) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up...")

        # Close storage connections
        if ctx.hot_storage:
            try:
                ctx.hot_storage.close()
            except Exception as e:
                logger.warning(f"Error closing hot storage: {e}")

        # Remove cloned repository if configured
        if ctx.config.cleanup_on_complete and ctx.repo_path:
            cleanup_repository(ctx.repo_path)

        logger.info("Cleanup complete")


# Convenience function for simple usage
def run_pipeline(
    codebase_id: str,
    clone_url: str,
    repo_owner: str,
    repo_name: str,
    organization_id: str = "default",
    work_dir: Path | None = None,
    auth_token: str | None = None
) -> PipelineOutput:
    """
    Run analytics pipeline with default configuration.

    Args:
        codebase_id: Codebase UUID
        clone_url: Git clone URL
        repo_owner: Repository owner
        repo_name: Repository name
        organization_id: Organization UUID
        work_dir: Working directory (default: /tmp/analytics)
        auth_token: Optional auth token for private repos

    Returns:
        PipelineOutput with results
    """
    config = PipelineConfig(
        work_dir=work_dir or Path("/tmp/analytics")
    )

    pipeline = AnalyticsPipeline(config)

    return pipeline.run(PipelineInput(
        codebase_id=codebase_id,
        organization_id=organization_id,
        clone_url=clone_url,
        repo_owner=repo_owner,
        repo_name=repo_name,
        auth_token=auth_token
    ))

