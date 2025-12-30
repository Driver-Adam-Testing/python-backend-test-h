# Analytics Service

Git repository analytics pipeline for Driver.

## Overview

This service provides automated git repository analytics:
- Commit extraction and processing
- Branch discovery and tracking
- Metrics aggregation (daily, monthly, contributors)
- Code ownership calculation
- JSON export for API consumption

## Architecture

```
analytics/
├── src/
│   ├── pipeline/           # Pipeline orchestration
│   │   ├── orchestrator.py # Main entry point
│   │   └── phases/         # Individual pipeline phases
│   ├── storage/            # DuckDB + Parquet storage
│   ├── aggregation/        # Metrics computation
│   ├── schemas/            # Data schemas
│   ├── sloc/               # SLOC calculation
│   ├── export/             # JSON export
│   └── models/             # Pydantic models
└── tests/
    ├── fixtures/           # Test data generators
    ├── unit/               # Unit tests
    └── integration/        # E2E tests
```

## Pipeline Flow

```
Clone → Extract → Branches → Aggregate → Ownership → Export → Upload
```

## Usage

```python
from src.pipeline.orchestrator import AnalyticsPipeline, PipelineConfig, PipelineInput

config = PipelineConfig(work_dir=Path("/tmp/analytics"))
pipeline = AnalyticsPipeline(config)

result = pipeline.run(PipelineInput(
    codebase_id="uuid-here",
    organization_id="org-uuid",
    clone_url="https://github.com/owner/repo",
    repo_owner="owner",
    repo_name="repo",
))

if result.success:
    print(f"Processed {result.total_commits} commits")
```

## Development

```bash
cd content_services/analytics
poetry install
poetry run pytest tests/ -v
```

## Dependencies

- `duckdb`: Hot storage for aggregated metrics
- `pyarrow`: Parquet storage for commit data
- `pygit2`: Git operations via libgit2
- `pandas`: Data manipulation
- `pydantic`: Data validation

