"""
Base adapter interface for git hosting providers.

This module defines the abstract interface that all git server adapters must implement.
It ensures consistency across different providers (GitHub, GitLab, Bitbucket, etc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class PRInfo:
    """Data class representing Pull Request information."""

    number: int
    title: str
    description: str
    source_branch: str
    target_branch: str
    author: str
    state: str
    created_at: str
    updated_at: str
    html_url: str


@dataclass
class FileChange:
    """Data class representing a changed file in a PR."""

    filename: str
    status: str  # added, modified, removed, renamed
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None


@dataclass
class ReviewComment:
    """Data class representing a review comment."""

    body: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    position: Optional[int] = None  # Position in diff
    severity: str = "info"  # info, warning, error


class BaseAdapter(ABC):
    """Abstract base class for git hosting provider adapters."""

    def __init__(self, token: Optional[str] = None, api_url: Optional[str] = None):
        """
        Initialize the adapter.

        Args:
            token: API token for authentication
            api_url: Base API URL (for self-hosted instances)
        """
        self.token = token
        self.api_url = api_url

    @abstractmethod
    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> PRInfo:
        """
        Get pull request information.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            PRInfo object with PR details
        """
        pass

    @abstractmethod
    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[FileChange]:
        """
        Get list of files changed in a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of FileChange objects
        """
        pass

    @abstractmethod
    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """
        Get the unified diff for a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Unified diff as string
        """
        pass

    @abstractmethod
    def post_review_comment(
        self, owner: str, repo: str, pr_number: int, body: str
    ) -> Dict[str, Any]:
        """
        Post a general review comment on the pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Comment body

        Returns:
            API response data
        """
        pass

    @abstractmethod
    def post_inline_comment(
        self, owner: str, repo: str, pr_number: int, comment: ReviewComment
    ) -> Dict[str, Any]:
        """
        Post an inline comment on a specific line in the PR.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            comment: ReviewComment object with position and content

        Returns:
            API response data
        """
        pass

    @abstractmethod
    def validate_credentials(self) -> bool:
        """
        Validate API credentials.

        Returns:
            True if credentials are valid, False otherwise
        """
        pass

    def get_file_content(self, owner: str, repo: str, file_path: str, ref: str) -> str:
        """
        Get file content at a specific commit/branch.

        This is optional for basic functionality but useful for enhanced analysis.

        Args:
            owner: Repository owner
            repo: Repository name
            file_path: Path to the file
            ref: Git reference (commit SHA, branch name)

        Returns:
            File content as string
        """
        raise NotImplementedError(
            "File content retrieval not implemented for this adapter"
        )
