"""End-to-end integration tests for analytics pipeline."""
import tempfile
from pathlib import Path

import pytest
import pygit2

from src.pipeline.orchestrator import (
    AnalyticsPipeline,
    PipelineConfig,
    PipelineInput,
    PipelineOutput,
)
from src.pipeline.phases.clone import open_repository
from src.pipeline.phases.extract import extract_commits
from src.pipeline.phases.branches import discover_branches


class TestPipelinePhases:
    """Test individual pipeline phases."""

    @pytest.fixture
    def test_repo(self, tmp_path):
        """Create a test git repository."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        
        repo = pygit2.init_repository(str(repo_path), bare=False)
        
        # Configure
        config = repo.config
        config["user.name"] = "Test"
        config["user.email"] = "test@example.com"
        
        # Create initial commit
        readme = repo_path / "README.md"
        readme.write_text("# Test Repo\n")
        
        index = repo.index
        index.add("README.md")
        index.write()
        tree = index.write_tree()
        
        sig = pygit2.Signature("Test", "test@example.com")
        repo.create_commit("HEAD", sig, sig, "Initial commit", tree, [])
        
        # Add more commits
        for i in range(5):
            test_file = repo_path / f"file_{i}.py"
            test_file.write_text(f"# File {i}\nprint('hello {i}')\n")
            
            index = repo.index
            index.add(f"file_{i}.py")
            index.write()
            tree = index.write_tree()
            
            parent = repo.head.peel(pygit2.Commit)
            repo.create_commit("HEAD", sig, sig, f"Add file {i}", tree, [parent.id])
        
        return repo_path, repo

    def test_open_repository(self, test_repo):
        """Test opening an existing repository."""
        repo_path, _ = test_repo
        
        result = open_repository(repo_path)
        
        assert result.success
        assert result.repo is not None
        assert result.repo_path == repo_path

    def test_extract_commits(self, test_repo):
        """Test extracting commits from repository."""
        repo_path, repo = test_repo
        
        result = extract_commits(
            repo=repo,
            codebase_id="test-uuid",
            include_patches=True
        )
        
        assert result.success
        assert result.total_commits == 6  # 1 initial + 5 more
        assert len(result.commits) >= 6  # May have duplicates per branch

    def test_discover_branches(self, test_repo):
        """Test discovering branches."""
        repo_path, repo = test_repo
        
        result = discover_branches(repo)
        
        assert result.success
        assert len(result.branches) >= 1
        assert result.default_branch in ["main", "master"]


class TestPipelineIntegration:
    """Integration tests for full pipeline."""

    @pytest.fixture
    def pipeline_with_repo(self, tmp_path):
        """Create pipeline config and a test repository."""
        # Create work directory
        work_dir = tmp_path / "analytics"
        work_dir.mkdir()
        
        # Create test repository
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        
        repo = pygit2.init_repository(str(repo_path), bare=False)
        
        config = repo.config
        config["user.name"] = "Test"
        config["user.email"] = "test@example.com"
        
        # Create initial commit
        readme = repo_path / "README.md"
        readme.write_text("# Test\n")
        
        index = repo.index
        index.add("README.md")
        index.write()
        tree = index.write_tree()
        
        sig = pygit2.Signature("Test", "test@example.com")
        repo.create_commit("HEAD", sig, sig, "Initial", tree, [])
        
        # Add commits
        for i in range(3):
            f = repo_path / f"f{i}.py"
            f.write_text(f"x = {i}\n")
            
            index = repo.index
            index.add(f"f{i}.py")
            index.write()
            tree = index.write_tree()
            
            parent = repo.head.peel(pygit2.Commit)
            repo.create_commit("HEAD", sig, sig, f"C{i}", tree, [parent.id])
        
        pipeline_config = PipelineConfig(
            work_dir=work_dir,
            cleanup_on_complete=False  # Keep for inspection
        )
        
        return pipeline_config, repo_path

    def test_pipeline_with_local_repo(self, pipeline_with_repo):
        """Test pipeline can process a local repository path.
        
        Note: This test uses a local path instead of clone URL.
        The actual pipeline would clone from URL, but we test the
        phases work correctly with a local repo.
        """
        config, repo_path = pipeline_with_repo
        
        # Open the local repo directly
        result = open_repository(repo_path)
        assert result.success
        
        # Extract commits
        extract_result = extract_commits(
            repo=result.repo,
            codebase_id="test-uuid",
            include_patches=False
        )
        
        assert extract_result.success
        assert extract_result.total_commits == 4  # Initial + 3 more
        
        # Discover branches
        branches_result = discover_branches(result.repo)
        
        assert branches_result.success
        assert len(branches_result.branches) >= 1

