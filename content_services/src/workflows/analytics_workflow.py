"""
Analytics Hatchet workflow.

Triggers the analytics pipeline for a codebase to generate
JSON analytics files for the frontend.
"""

from datetime import timedelta
from pathlib import Path

from hatchet_client import hatchet
from hatchet_sdk import Context
from hatchet_sdk.runnables.types import ConcurrencyExpression, ConcurrencyLimitStrategy
from pydantic import BaseModel


class AnalyticsInput(BaseModel):
    """Input for analytics workflow."""
    codebase_id: str
    organization_id: str
    clone_url: str
    repo_owner: str
    repo_name: str
    auth_token: str | None = None


@hatchet.task(
    name="analytics-workflow",
    execution_timeout=timedelta(minutes=120),  # 2 hours max
    concurrency=ConcurrencyExpression(
        max_runs=3,
        expression="'analytics-workflow'",
        limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
    ),
)
async def analytics_task(input: AnalyticsInput, ctx: Context) -> dict[str, str]:
    """
    Run analytics pipeline for a codebase.

    This task:
    1. Clones the repository
    2. Extracts commit and branch data
    3. Builds aggregated metrics
    4. Exports JSON files for the API
    5. Uploads to S3 (future)

    Args:
        input: AnalyticsInput with repository details
        ctx: Hatchet context

    Returns:
        Dictionary with status and metrics
    """
    # Import from analytics service (installed as package in content_services)
    import sys
    sys.path.insert(0, "/app/analytics")
    from src.pipeline.orchestrator import (
        AnalyticsPipeline,
        PipelineConfig,
        PipelineInput
    )

    print(f"Starting analytics task for codebase {input.codebase_id}")

    # Configure pipeline
    config = PipelineConfig(
        work_dir=Path("/tmp/analytics"),
        cleanup_on_complete=True,
        default_branch_only=False,
        include_patches=True
    )

    pipeline = AnalyticsPipeline(config)

    # Run pipeline
    result = pipeline.run(PipelineInput(
        codebase_id=input.codebase_id,
        organization_id=input.organization_id,
        clone_url=input.clone_url,
        repo_owner=input.repo_owner,
        repo_name=input.repo_name,
        auth_token=input.auth_token
    ))

    if not result.success:
        print(f"Analytics task failed: {result.error}")
        return {
            "status": "failed",
            "error": result.error or "Unknown error",
            "codebase_id": input.codebase_id
        }

    print(f"Analytics task completed: {result.total_commits} commits, "
          f"{result.total_branches} branches in {result.duration_seconds:.1f}s")

    return {
        "status": "complete",
        "codebase_id": input.codebase_id,
        "total_commits": str(result.total_commits),
        "total_branches": str(result.total_branches),
        "total_contributors": str(result.total_contributors),
        "duration_seconds": f"{result.duration_seconds:.1f}",
        "json_files": str(len(result.json_files))
    }

