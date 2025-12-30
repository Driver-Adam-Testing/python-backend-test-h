"""
Extract phase: Extract commit data from repository using pygit2.

This phase collects commit metadata and calculates SLOC metrics.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import pygit2

from src.sloc.calculator import DualSLOCCalculator, SLOCMetrics

logger = logging.getLogger(__name__)


@dataclass
class ExtractResult:
    """Result of commit extraction."""
    success: bool
    commits: list[dict]
    total_commits: int
    error: str | None = None


def extract_commits(
    repo: pygit2.Repository,
    codebase_id: str,
    branch_names: list[str] | None = None,
    include_patches: bool = True
) -> ExtractResult:
    """
    Extract commits from repository.

    Args:
        repo: pygit2.Repository instance
        codebase_id: Codebase UUID
        branch_names: List of branches to extract from (None = all)
        include_patches: Whether to include patch data for SLOC

    Returns:
        ExtractResult with commit data
    """
    logger.info(f"Extracting commits for codebase {codebase_id}")

    try:
        # Get branches to process
        if branch_names is None:
            branch_names = _get_all_branch_names(repo)

        logger.info(f"Processing {len(branch_names)} branches: {branch_names[:5]}...")

        # Collect commits from all branches
        all_commits = []
        commit_shas_by_branch: dict[str, set[str]] = {}

        for branch_name in branch_names:
            branch_shas = _get_commits_in_branch(repo, branch_name)
            commit_shas_by_branch[branch_name] = branch_shas
            logger.debug(f"Branch {branch_name}: {len(branch_shas)} commits")

        # Get unique commit SHAs across all branches
        all_sha_set = set()
        for shas in commit_shas_by_branch.values():
            all_sha_set.update(shas)

        logger.info(f"Found {len(all_sha_set)} unique commits")

        # Process each commit
        collected_at = datetime.now(timezone.utc)

        for i, commit_sha in enumerate(all_sha_set):
            if (i + 1) % 100 == 0:
                logger.debug(f"Processing commit {i + 1}/{len(all_sha_set)}")

            try:
                # Get branches this commit belongs to
                commit_branches = [
                    branch for branch, shas in commit_shas_by_branch.items()
                    if commit_sha in shas
                ]

                # Extract commit data
                commit_data = _extract_commit_data(
                    repo, commit_sha, codebase_id, commit_branches,
                    collected_at, include_patches
                )

                if commit_data:
                    all_commits.extend(commit_data)

            except Exception as e:
                logger.warning(f"Error processing commit {commit_sha[:8]}: {e}")
                continue

        logger.info(f"Successfully extracted {len(all_commits)} commit records")

        return ExtractResult(
            success=True,
            commits=all_commits,
            total_commits=len(all_sha_set)
        )

    except Exception as e:
        error_msg = f"Failed to extract commits: {e}"
        logger.error(error_msg)
        return ExtractResult(
            success=False,
            commits=[],
            total_commits=0,
            error=error_msg
        )


def _get_all_branch_names(repo: pygit2.Repository) -> list[str]:
    """Get all branch names (local + remote, deduplicated)."""
    branch_names = set()

    # Add local branches
    for branch_name in repo.branches.local:
        branch_names.add(branch_name)

    # Add remote branches (strip "origin/" prefix)
    for remote_branch in repo.branches.remote:
        if "/" in remote_branch:
            branch_name = remote_branch.split("/", 1)[1]
            if branch_name.upper() != "HEAD":
                branch_names.add(branch_name)

    return sorted(list(branch_names))


def _get_commits_in_branch(repo: pygit2.Repository, branch_name: str) -> set[str]:
    """Get all commit SHAs in a branch."""
    # Try to get branch reference (local first, then remote)
    branch_ref = None
    if branch_name in repo.branches.local:
        branch_ref = repo.branches[branch_name]
    elif f"origin/{branch_name}" in repo.branches.remote:
        branch_ref = repo.branches[f"origin/{branch_name}"]
    else:
        logger.warning(f"Branch not found: {branch_name}")
        return set()

    # Walk commits in branch
    commit_shas = set()
    try:
        for commit in repo.walk(
            branch_ref.target,
            pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME
        ):
            commit_shas.add(str(commit.id))
    except Exception as e:
        logger.warning(f"Error walking branch {branch_name}: {e}")

    return commit_shas


def _extract_commit_data(
    repo: pygit2.Repository,
    commit_sha: str,
    codebase_id: str,
    branches: list[str],
    collected_at: datetime,
    include_patches: bool
) -> list[dict]:
    """
    Extract data for a single commit.

    Returns one record per branch the commit belongs to.
    """
    try:
        commit = repo.get(commit_sha)
        if not commit:
            return []

        # Get diff from parent
        diff = _get_commit_diff(repo, commit)

        # Calculate line/byte metrics from diff
        files_changed = 0
        total_additions = 0
        total_deletions = 0
        total_addition_bytes = 0
        total_deletion_bytes = 0

        if diff:
            # Use diff.stats for line counts (most reliable)
            stats = diff.stats
            files_changed = stats.files_changed
            total_additions = stats.insertions
            total_deletions = stats.deletions
            
            # Calculate bytes from patch content if requested
            if include_patches:
                try:
                    patch_text = diff.patch
                    if patch_text:
                        for line in patch_text.split('\n'):
                            if line.startswith('+') and not line.startswith('+++'):
                                total_addition_bytes += len(line[1:].encode('utf-8', errors='replace'))
                            elif line.startswith('-') and not line.startswith('---'):
                                total_deletion_bytes += len(line[1:].encode('utf-8', errors='replace'))
                except Exception:
                    # Fall back to estimate
                    total_addition_bytes = total_additions * 50
                    total_deletion_bytes = total_deletions * 50
            else:
                total_addition_bytes = total_additions * 50
                total_deletion_bytes = total_deletions * 50

        # Calculate derived metrics
        net_lines = total_additions - total_deletions
        churn_lines = total_additions + total_deletions
        patch_bytes = total_addition_bytes + total_deletion_bytes
        net_bytes = total_addition_bytes - total_deletion_bytes
        sloc = patch_bytes // 50
        bytes_per_line = patch_bytes / churn_lines if churn_lines > 0 else 0.0

        # Categorize commit size
        if churn_lines < 10:
            size_category = "tiny"
        elif churn_lines < 50:
            size_category = "small"
        elif churn_lines < 200:
            size_category = "medium"
        else:
            size_category = "large"

        # Get commit timestamp
        commit_time = datetime.fromtimestamp(commit.commit_time, tz=timezone.utc)

        # Create base commit record
        base_record = {
            'commit_sha': commit_sha,
            'codebase_id': codebase_id,
            'committed_at': commit_time,
            'collected_at': collected_at,
            'commit_date': commit_time.date(),
            'commit_year': commit_time.year,
            'commit_month': commit_time.month,
            'commit_day': commit_time.day,
            'author_email': commit.author.email,
            'author_name': commit.author.name,
            'committer_email': commit.committer.email,
            'committer_name': commit.committer.name,
            'message': commit.message[:1000] if commit.message else "",
            'message_length': len(commit.message) if commit.message else 0,
            'parent_count': len(commit.parents),
            'is_merge_commit': len(commit.parents) > 1,
            'files_changed': files_changed,
            'additions_lines': total_additions,
            'deletions_lines': total_deletions,
            'net_lines': net_lines,
            'churn_lines': churn_lines,
            'addition_bytes': total_addition_bytes,
            'deletion_bytes': total_deletion_bytes,
            'patch_bytes': patch_bytes,
            'net_bytes': net_bytes,
            'sloc': sloc,
            'bytes_per_line': bytes_per_line,
            'commit_size_category': size_category,
            'is_refactor': total_additions > 0 and total_deletions > 0 and abs(net_lines) < churn_lines * 0.1,
            'collection_version': '2.0'
        }

        # Create one record per branch
        records = []
        for branch in branches:
            record = base_record.copy()
            record['branch_name'] = branch
            records.append(record)

        return records

    except Exception as e:
        logger.warning(f"Error extracting commit {commit_sha[:8]}: {e}")
        return []


def _get_commit_diff(repo: pygit2.Repository, commit: pygit2.Commit) -> pygit2.Diff | None:
    """Get diff for a commit compared to its parent."""
    try:
        if commit.parents:
            # Normal commit: diff against first parent
            parent = commit.parents[0]
            return repo.diff(parent.tree, commit.tree)
        else:
            # First commit: diff against empty tree
            tree_builder = repo.TreeBuilder()
            empty_tree_oid = tree_builder.write()
            empty_tree = repo.get(empty_tree_oid)
            return repo.diff(empty_tree, commit.tree)
    except Exception as e:
        logger.debug(f"Error getting diff for commit {commit.id}: {e}")
        return None

