"""
Create a fixture repository with known metrics for testing.

This follows the GitStats pattern of having predetermined commits, branches,
and metrics that can be validated against.
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

import pygit2


class FixtureRepoBuilder:
    """Build a git repository with known characteristics for testing."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.repo: pygit2.Repository | None = None
        self.commit_shas: Dict[str, str] = {}
        self.base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def create(self) -> Dict[str, Any]:
        """
        Create the fixture repository with all commits and branches.

        Returns:
            Dictionary containing commit SHAs and expected metrics
        """
        if self.repo_path.exists():
            shutil.rmtree(self.repo_path)

        self.repo_path.mkdir(parents=True)
        self.repo = pygit2.init_repository(str(self.repo_path), bare=False)

        # Configure git
        config = self.repo.config
        config["user.name"] = "Alice"
        config["user.email"] = "alice@example.com"

        # Create main branch commits
        self._create_main_commits()

        # Create feature branches
        self._create_feature_branch()

        return self._get_expected_metrics()

    def _create_main_commits(self):
        """Create 5 commits on main branch."""
        sig = pygit2.Signature("Alice", "alice@example.com")

        for i in range(5):
            content = f"# Main content {i}\n" * (10 + i * 5)
            blob_oid = self.repo.create_blob(content.encode())

            # Build tree with this file
            if i == 0:
                builder = self.repo.TreeBuilder()
            else:
                parent = self.repo.head.peel()
                builder = self.repo.TreeBuilder(parent.tree)

            builder.insert(f"main_{i}.py", blob_oid, pygit2.GIT_FILEMODE_BLOB)
            tree_oid = builder.write()

            parents = [] if i == 0 else [self.repo.head.target]
            ref = "refs/heads/main" if i == 0 else "HEAD"

            commit_oid = self.repo.create_commit(
                ref, sig, sig, f"Main commit {i}", tree_oid, parents
            )
            self.commit_shas[f"main_{i}"] = str(commit_oid)

    def _create_feature_branch(self):
        """Create feature branch with 3 commits."""
        base = self.repo.get(self.commit_shas["main_2"])
        self.repo.create_branch("feature", base)
        self.repo.checkout(self.repo.branches["feature"])

        sig = pygit2.Signature("Bob", "bob@example.com")

        for i in range(3):
            content = f"# Feature content {i}\n" * (15 + i * 3)
            blob_oid = self.repo.create_blob(content.encode())

            parent = self.repo.head.peel()
            builder = self.repo.TreeBuilder(parent.tree)
            builder.insert(f"feature_{i}.py", blob_oid, pygit2.GIT_FILEMODE_BLOB)
            tree_oid = builder.write()

            commit_oid = self.repo.create_commit(
                "HEAD", sig, sig, f"Feature commit {i}",
                tree_oid, [self.repo.head.target]
            )
            self.commit_shas[f"feature_{i}"] = str(commit_oid)

        # Return to main
        self.repo.checkout(self.repo.branches["main"])

    def _get_expected_metrics(self) -> Dict[str, Any]:
        """Return expected metrics for validation."""
        return {
            "commit_shas": self.commit_shas,
            "repository": {
                "total_commits": 8,  # 5 main + 3 feature
                "total_contributors": 2,  # Alice, Bob
                "total_branches": 2,  # main, feature
            },
            "branches": {
                "main": {
                    "total_commits": 5,
                    "unique_commits": 5,
                    "contributors": ["alice@example.com"],
                },
                "feature": {
                    "total_commits": 6,  # 3 from main (up to main_2) + 3 new
                    "unique_commits": 3,
                    "contributors": ["bob@example.com"],
                },
            },
        }


def create_fixture_repository(output_dir: Path | None = None) -> Dict[str, Any]:
    """Create a fixture repository for testing."""
    if output_dir is None:
        output_dir = Path("/tmp/analytics-test-fixture")

    builder = FixtureRepoBuilder(output_dir)
    return builder.create()


# For pytest fixture usage
import pytest


@pytest.fixture(scope="function")
def fixture_repo_with_metrics(temp_dir):
    """
    Create a fixture repository with known metrics.

    Returns:
        Tuple of (repo_path, expected_metrics)
    """
    repo_path = temp_dir / "fixture_repo"
    builder = FixtureRepoBuilder(repo_path)
    expected = builder.create()
    return repo_path, expected

