"""
GitHub adapter implementation for the PR Review Agent.

This module provides GitHub-specific implementation of the BaseAdapter interface.
It handles GitHub API interactions for fetching PR data and posting comments.
"""

import os
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime

from .base_adapter import BaseAdapter, PRInfo, FileChange, ReviewComment


class GitHubAdapter(BaseAdapter):
    """GitHub implementation of the BaseAdapter interface."""

    def __init__(self, token: Optional[str] = None, api_url: Optional[str] = None):
        """
        Initialize GitHub adapter.

        Args:
            token: GitHub personal access token
            api_url: GitHub API URL (defaults to public GitHub)
        """
        super().__init__(token, api_url)
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.api_url = api_url or os.environ.get(
            "GITHUB_API_URL", "https://api.github.com"
        )

        if not self.token:
            raise ValueError(
                "GitHub token is required. Set GITHUB_TOKEN environment variable or pass token parameter."
            )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> PRInfo:
        """Get pull request information from GitHub."""
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        response = self.session.get(url)
        response.raise_for_status()

        data = response.json()

        return PRInfo(
            number=data["number"],
            title=data["title"],
            description=data["body"] or "",
            source_branch=data["head"]["ref"],
            target_branch=data["base"]["ref"],
            author=data["user"]["login"],
            state=data["state"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            html_url=data["html_url"],
        )

    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[FileChange]:
        """Get list of files changed in the pull request."""
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        response = self.session.get(url)
        response.raise_for_status()

        files_data = response.json()
        file_changes = []

        for file_data in files_data:
            file_change = FileChange(
                filename=file_data["filename"],
                status=file_data["status"],
                additions=file_data["additions"],
                deletions=file_data["deletions"],
                changes=file_data["changes"],
                patch=file_data.get("patch"),
            )
            file_changes.append(file_change)

        return file_changes

    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Get the unified diff for the pull request."""
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {"Accept": "application/vnd.github.v3.diff"}

        response = self.session.get(url, headers=headers)
        response.raise_for_status()

        return response.text

    def post_review_comment(
        self, owner: str, repo: str, pr_number: int, body: str
    ) -> Dict[str, Any]:
        """Post a general review comment on the pull request."""
        url = f"{self.api_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        payload = {"body": body}

        response = self.session.post(url, json=payload)
        response.raise_for_status()

        return response.json()

    def post_inline_comment(
        self, owner: str, repo: str, pr_number: int, comment: ReviewComment
    ) -> Dict[str, Any]:
        """Post an inline comment on a specific line in the PR."""
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments"

        payload = {
            "body": comment.body,
            "path": comment.file_path,
        }

        # GitHub uses position for diff position
        if comment.position is not None:
            payload["position"] = comment.position
        elif comment.line_number is not None:
            # For line-based comments, we need the commit SHA
            pr_info = self.get_pr_info(owner, repo, pr_number)
            payload["line"] = comment.line_number
            payload["side"] = "RIGHT"  # Comment on the new version

        response = self.session.post(url, json=payload)
        response.raise_for_status()

        return response.json()

    def validate_credentials(self) -> bool:
        """Validate GitHub API credentials."""
        try:
            url = f"{self.api_url}/user"
            response = self.session.get(url)
            return response.status_code == 200
        except Exception:
            return False

    def get_file_content(self, owner: str, repo: str, file_path: str, ref: str) -> str:
        """Get file content at a specific commit/branch."""
        url = f"{self.api_url}/repos/{owner}/{repo}/contents/{file_path}"
        params = {"ref": ref}

        response = self.session.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        # GitHub returns base64 encoded content
        import base64

        if data["encoding"] == "base64":
            return base64.b64decode(data["content"]).decode("utf-8")
        else:
            return data["content"]

    def create_pull_request_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        comments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Create a pull request review with optional inline comments.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Review summary
            event: Review event type (COMMENT, APPROVE, REQUEST_CHANGES)
            comments: List of inline comments

        Returns:
            API response data
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"

        payload = {"body": body, "event": event}

        if comments:
            payload["comments"] = comments

        response = self.session.post(url, json=payload)
        response.raise_for_status()

        return response.json()


if __name__ == "__main__":
    # Example usage
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Initialize adapter
    adapter = GitHubAdapter()

    # Validate credentials
    if adapter.validate_credentials():
        print("✅ GitHub credentials are valid")

        # Example: Get PR info (replace with actual values)
        # pr_info = adapter.get_pr_info("owner", "repo", 1)
        # print(f"PR Title: {pr_info.title}")

    else:
        print("❌ GitHub credentials are invalid")
