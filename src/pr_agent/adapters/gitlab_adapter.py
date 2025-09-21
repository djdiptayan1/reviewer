"""
GitLab adapter implementation for the PR Review Agent.

This is a stub implementation that shows the structure for GitLab integration.
In a full implementation, this would use the GitLab API to interact with merge requests.
"""

import os
import requests
from typing import Dict, List, Any, Optional

from .base_adapter import BaseAdapter, PRInfo, FileChange, ReviewComment


class GitLabAdapter(BaseAdapter):
    """GitLab implementation of the BaseAdapter interface (stub)."""

    def __init__(self, token: Optional[str] = None, api_url: Optional[str] = None):
        """Initialize GitLab adapter."""
        super().__init__(token, api_url)
        self.token = token or os.environ.get("GITLAB_TOKEN")
        self.api_url = api_url or os.environ.get(
            "GITLAB_API_URL", "https://gitlab.com/api/v4"
        )

        if not self.token:
            raise ValueError(
                "GitLab token is required. Set GITLAB_TOKEN environment variable."
            )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
        )

    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> PRInfo:
        """Get merge request information from GitLab."""
        # In GitLab, projects are identified by project_id or namespace/project_name
        project_path = f"{owner}/{repo}"
        url = f"{self.api_url}/projects/{project_path.replace('/', '%2F')}/merge_requests/{pr_number}"

        response = self.session.get(url)
        response.raise_for_status()

        data = response.json()

        return PRInfo(
            number=data["iid"],
            title=data["title"],
            description=data["description"] or "",
            source_branch=data["source_branch"],
            target_branch=data["target_branch"],
            author=data["author"]["username"],
            state=data["state"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            html_url=data["web_url"],
        )

    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[FileChange]:
        """Get list of files changed in the merge request."""
        project_path = f"{owner}/{repo}"
        url = f"{self.api_url}/projects/{project_path.replace('/', '%2F')}/merge_requests/{pr_number}/changes"

        response = self.session.get(url)
        response.raise_for_status()

        data = response.json()
        file_changes = []

        for change in data.get("changes", []):
            # GitLab change structure is different from GitHub
            file_change = FileChange(
                filename=change["new_path"] or change["old_path"],
                status="modified",  # GitLab doesn't provide status in the same way
                additions=0,  # Would need to parse diff to get actual counts
                deletions=0,
                changes=0,
                patch=change.get("diff"),
            )
            file_changes.append(file_change)

        return file_changes

    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Get the unified diff for the merge request."""
        project_path = f"{owner}/{repo}"
        url = f"{self.api_url}/projects/{project_path.replace('/', '%2F')}/merge_requests/{pr_number}/changes"

        response = self.session.get(url)
        response.raise_for_status()

        data = response.json()

        # Combine all file diffs
        diff_text = ""
        for change in data.get("changes", []):
            if change.get("diff"):
                diff_text += change["diff"] + "\n"

        return diff_text

    def post_review_comment(
        self, owner: str, repo: str, pr_number: int, body: str
    ) -> Dict[str, Any]:
        """Post a general comment on the merge request."""
        project_path = f"{owner}/{repo}"
        url = f"{self.api_url}/projects/{project_path.replace('/', '%2F')}/merge_requests/{pr_number}/notes"

        payload = {"body": body}

        response = self.session.post(url, json=payload)
        response.raise_for_status()

        return response.json()

    def post_inline_comment(
        self, owner: str, repo: str, pr_number: int, comment: ReviewComment
    ) -> Dict[str, Any]:
        """Post an inline comment on a specific line in the MR."""
        project_path = f"{owner}/{repo}"
        url = f"{self.api_url}/projects/{project_path.replace('/', '%2F')}/merge_requests/{pr_number}/discussions"

        # GitLab uses position objects for line comments
        position_data = {
            "base_sha": "base_commit_sha",  # Would need to get from MR
            "start_sha": "start_commit_sha",
            "head_sha": "head_commit_sha",
            "position_type": "text",
            "new_path": comment.file_path,
            "new_line": comment.line_number,
        }

        payload = {"body": comment.body, "position": position_data}

        response = self.session.post(url, json=payload)
        response.raise_for_status()

        return response.json()

    def validate_credentials(self) -> bool:
        """Validate GitLab API credentials."""
        try:
            url = f"{self.api_url}/user"
            response = self.session.get(url)
            return response.status_code == 200
        except Exception:
            return False
