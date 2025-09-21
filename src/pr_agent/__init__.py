"""
PR Review Agent - AI-powered Pull Request Review System

A modular Python agent that can review Pull Requests across multiple git servers
(GitHub, GitLab, Bitbucket), analyze diffs, run automated checks, and provide
AI-driven feedback with inline comments.
"""

__version__ = "1.0.0"
__author__ = "PR Review Agent Team"
__description__ = "AI-powered Pull Request Review Agent"

from .config import ConfigManager, PRAgentConfig
from .diff_parser import DiffParser
from .reporter import Reporter

__all__ = ["ConfigManager", "PRAgentConfig", "DiffParser", "Reporter"]
