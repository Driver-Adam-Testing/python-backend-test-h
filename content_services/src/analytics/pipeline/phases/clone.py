"""
Clone phase: Clone repository using pygit2.

This phase clones a repository to a local path for analysis.
Uses pygit2 directly for efficient Git operations.
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

import pygit2

logger = logging.getLogger(__name__)


@dataclass
class CloneResult:
    """Result of clone operation."""
    success: bool
    repo_path: Path | None
    repo: pygit2.Repository | None
    error: str | None = None


def clone_repository(
    clone_url: str,
    target_path: Path,
    auth_token: str | None = None,
    clean_existing: bool = True
) -> CloneResult:
    """
    Clone a repository using pygit2.

    Args:
        clone_url: Git clone URL (HTTPS)
        target_path: Local path to clone into
        auth_token: Optional authentication token (for private repos)
        clean_existing: If True, remove existing directory before cloning

    Returns:
        CloneResult with repository path and pygit2.Repository instance
    """
    logger.info(f"Cloning repository from {clone_url} to {target_path}")

    try:
        # Clean up existing directory if requested
        if clean_existing and target_path.exists():
            logger.debug(f"Removing existing directory: {target_path}")
            shutil.rmtree(target_path)

        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Set up callbacks for authentication if token provided
        callbacks = None
        if auth_token:
            callbacks = _create_auth_callbacks(auth_token)

        # Clone the repository
        logger.info(f"Starting clone operation...")
        repo = pygit2.clone_repository(
            clone_url,
            str(target_path),
            callbacks=callbacks
        )

        logger.info(f"Successfully cloned repository to {target_path}")

        return CloneResult(
            success=True,
            repo_path=target_path,
            repo=repo
        )

    except pygit2.GitError as e:
        error_msg = f"Git error during clone: {e}"
        logger.error(error_msg)
        return CloneResult(
            success=False,
            repo_path=None,
            repo=None,
            error=error_msg
        )
    except Exception as e:
        error_msg = f"Unexpected error during clone: {e}"
        logger.error(error_msg)
        return CloneResult(
            success=False,
            repo_path=None,
            repo=None,
            error=error_msg
        )


def open_repository(repo_path: Path) -> CloneResult:
    """
    Open an existing repository.

    Args:
        repo_path: Path to existing repository

    Returns:
        CloneResult with repository instance
    """
    logger.info(f"Opening repository at {repo_path}")

    try:
        if not repo_path.exists():
            return CloneResult(
                success=False,
                repo_path=None,
                repo=None,
                error=f"Repository path does not exist: {repo_path}"
            )

        repo = pygit2.Repository(str(repo_path))
        logger.info(f"Successfully opened repository at {repo_path}")

        return CloneResult(
            success=True,
            repo_path=repo_path,
            repo=repo
        )

    except pygit2.GitError as e:
        error_msg = f"Git error opening repository: {e}"
        logger.error(error_msg)
        return CloneResult(
            success=False,
            repo_path=None,
            repo=None,
            error=error_msg
        )


def cleanup_repository(repo_path: Path) -> None:
    """
    Clean up a cloned repository.

    Args:
        repo_path: Path to repository to remove
    """
    if repo_path and repo_path.exists():
        logger.info(f"Cleaning up repository at {repo_path}")
        try:
            shutil.rmtree(repo_path)
            logger.info(f"Successfully removed {repo_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up repository: {e}")


def _create_auth_callbacks(token: str) -> pygit2.RemoteCallbacks:
    """
    Create authentication callbacks for private repos.

    Args:
        token: GitHub/GitLab access token

    Returns:
        pygit2.RemoteCallbacks with credentials
    """

    def credentials_callback(url, username_from_url, allowed_types):
        if allowed_types & pygit2.GIT_CREDENTIAL_USERPASS_PLAINTEXT:
            return pygit2.UserPass(token, "x-oauth-basic")
        return None

    callbacks = pygit2.RemoteCallbacks(credentials=credentials_callback)
    return callbacks

