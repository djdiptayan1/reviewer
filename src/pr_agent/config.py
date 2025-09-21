"""
Configuration management for the PR Review Agent.

This module handles loading and validating configuration from environment
variables, config files, and command-line arguments.
"""

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from dotenv import load_dotenv


@dataclass
class GitServerConfig:
    """Configuration for a git server."""

    name: str
    api_url: str
    token: Optional[str] = None
    enabled: bool = True


@dataclass
class AnalyzerConfig:
    """Configuration for analyzers."""

    # Static analysis
    flake8_enabled: bool = True
    flake8_max_line_length: int = 88
    flake8_ignore: List[str] = field(default_factory=lambda: ["E203", "W503"])

    bandit_enabled: bool = True
    bandit_confidence: str = "medium"

    eslint_enabled: bool = True
    eslint_config_file: Optional[str] = None

    mypy_enabled: bool = False
    mypy_strict: bool = False

    # AI analysis
    ai_enabled: bool = True
    ai_model: str = "gemini-1.5-flash"
    ai_temperature: float = 0.1
    ai_max_tokens: int = 2000

    # Security patterns
    security_patterns_enabled: bool = True


@dataclass
class ReviewConfig:
    """Configuration for review behavior."""

    post_summary: bool = True
    post_inline_comments: bool = True
    max_inline_comments: int = 20
    max_diff_size: int = 50000
    min_confidence_threshold: float = 0.7
    severity_filter: List[str] = field(
        default_factory=lambda: ["error", "warning", "suggestion"]
    )


@dataclass
class PRAgentConfig:
    """Main configuration for the PR Review Agent."""

    # Git servers
    github: GitServerConfig = field(
        default_factory=lambda: GitServerConfig(
            name="github", api_url="https://api.github.com"
        )
    )
    gitlab: GitServerConfig = field(
        default_factory=lambda: GitServerConfig(
            name="gitlab", api_url="https://gitlab.com/api/v4"
        )
    )
    bitbucket: GitServerConfig = field(
        default_factory=lambda: GitServerConfig(
            name="bitbucket", api_url="https://api.bitbucket.org/2.0"
        )
    )

    # Analysis configuration
    analyzers: AnalyzerConfig = field(default_factory=AnalyzerConfig)

    # Review configuration
    review: ReviewConfig = field(default_factory=ReviewConfig)

    # Gemini API key
    gemini_api_key: Optional[str] = None

    # Debug settings
    debug: bool = False
    verbose: bool = False


class ConfigManager:
    """Manages configuration loading and validation."""

    def __init__(self, config_file: Optional[str] = None, load_env: bool = True):
        """
        Initialize configuration manager.

        Args:
            config_file: Path to YAML config file
            load_env: Whether to load .env file
        """
        self.config_file = config_file

        if load_env:
            # Try to load .env from current directory or parent directories
            env_file = self._find_env_file()
            if env_file:
                load_dotenv(env_file)

        self.config = self._load_config()

    def get_config(self) -> PRAgentConfig:
        """Get the loaded configuration."""
        return self.config

    def get_git_server_config(self, provider: str) -> Optional[GitServerConfig]:
        """Get configuration for a specific git server provider."""
        provider_map = {
            "github": self.config.github,
            "gitlab": self.config.gitlab,
            "bitbucket": self.config.bitbucket,
        }
        return provider_map.get(provider.lower())

    def validate_config(self) -> List[str]:
        """
        Validate the configuration and return any errors.

        Returns:
            List of validation error messages
        """
        errors = []

        # Check for required API keys
        if self.config.analyzers.ai_enabled and not self.config.gemini_api_key:
            errors.append(
                "Gemini API key is required when AI analysis is enabled. Set GEMINI_API_KEY environment variable."
            )

        # Validate git server configurations
        for provider in ["github", "gitlab", "bitbucket"]:
            git_config = self.get_git_server_config(provider)
            if git_config and git_config.enabled and not git_config.token:
                env_var = f"{provider.upper()}_TOKEN"
                errors.append(
                    f"{provider.title()} token is required when {provider} is enabled. Set {env_var} environment variable."
                )

        # Validate numeric ranges
        if not 0.0 <= self.config.analyzers.ai_temperature <= 2.0:
            errors.append("AI temperature must be between 0.0 and 2.0")

        if self.config.analyzers.ai_max_tokens < 100:
            errors.append("AI max tokens must be at least 100")

        if not 0.0 <= self.config.review.min_confidence_threshold <= 1.0:
            errors.append("Minimum confidence threshold must be between 0.0 and 1.0")

        # Validate file paths
        if self.config.analyzers.eslint_config_file:
            if not Path(self.config.analyzers.eslint_config_file).exists():
                errors.append(
                    f"ESLint config file not found: {self.config.analyzers.eslint_config_file}"
                )

        return errors

    def update_from_args(self, args: Dict[str, Any]) -> None:
        """
        Update configuration from command-line arguments.

        Args:
            args: Dictionary of command-line arguments
        """
        # Map command-line args to config attributes
        arg_mapping = {
            "debug": "debug",
            "verbose": "verbose",
            "no_ai": ("analyzers", "ai_enabled", lambda x: not x),
            "no_static": ("analyzers", "flake8_enabled", lambda x: not x),
            "no_inline": ("review", "post_inline_comments", lambda x: not x),
            "no_summary": ("review", "post_summary", lambda x: not x),
            "ai_model": ("analyzers", "ai_model"),
            "max_comments": ("review", "max_inline_comments"),
            "confidence_threshold": ("review", "min_confidence_threshold"),
        }

        for arg_name, config_path in arg_mapping.items():
            if arg_name in args and args[arg_name] is not None:
                if isinstance(config_path, tuple):
                    # Nested config path
                    if len(config_path) == 3:
                        section, key, transform = config_path
                        value = transform(args[arg_name])
                    else:
                        section, key = config_path
                        value = args[arg_name]

                    section_obj = getattr(self.config, section)
                    setattr(section_obj, key, value)
                else:
                    # Direct config attribute
                    setattr(self.config, config_path, args[arg_name])

    def _load_config(self) -> PRAgentConfig:
        """Load configuration from various sources."""
        config = PRAgentConfig()

        # Load from config file if provided
        if self.config_file and Path(self.config_file).exists():
            config = self._load_from_file(self.config_file)

        # Override with environment variables
        self._load_from_environment(config)

        return config

    def _load_from_file(self, config_file: str) -> PRAgentConfig:
        """Load configuration from YAML file."""
        try:
            with open(config_file, "r") as f:
                data = yaml.safe_load(f)

            # Convert dict to dataclass
            return self._dict_to_config(data)

        except Exception as e:
            print(f"Warning: Failed to load config file {config_file}: {e}")
            return PRAgentConfig()

    def _load_from_environment(self, config: PRAgentConfig) -> None:
        """Load configuration from environment variables."""
        # Git server tokens
        config.github.token = os.getenv("GITHUB_TOKEN")
        config.gitlab.token = os.getenv("GITLAB_TOKEN")
        config.bitbucket.token = os.getenv("BITBUCKET_APP_PASSWORD")

        # Custom API URLs
        if os.getenv("GITHUB_API_URL"):
            config.github.api_url = os.getenv("GITHUB_API_URL")
        if os.getenv("GITLAB_API_URL"):
            config.gitlab.api_url = os.getenv("GITLAB_API_URL")
        if os.getenv("BITBUCKET_API_URL"):
            config.bitbucket.api_url = os.getenv("BITBUCKET_API_URL")

        # Gemini configuration
        config.gemini_api_key = os.getenv("GEMINI_API_KEY")

        if os.getenv("DEFAULT_AI_MODEL"):
            config.analyzers.ai_model = os.getenv("DEFAULT_AI_MODEL")

        # Review settings
        if os.getenv("MAX_DIFF_SIZE"):
            try:
                config.review.max_diff_size = int(os.getenv("MAX_DIFF_SIZE"))
            except ValueError:
                pass

        if os.getenv("ENABLE_INLINE_COMMENTS"):
            config.review.post_inline_comments = (
                os.getenv("ENABLE_INLINE_COMMENTS").lower() == "true"
            )

        if os.getenv("ENABLE_SECURITY_SCAN"):
            config.analyzers.security_patterns_enabled = (
                os.getenv("ENABLE_SECURITY_SCAN").lower() == "true"
            )

        # Debug settings
        if os.getenv("DEBUG"):
            config.debug = os.getenv("DEBUG").lower() == "true"

        if os.getenv("VERBOSE"):
            config.verbose = os.getenv("VERBOSE").lower() == "true"

    def _dict_to_config(self, data: Dict[str, Any]) -> PRAgentConfig:
        """Convert dictionary to PRAgentConfig dataclass."""
        # This is a simplified conversion - in a full implementation,
        # you'd want more robust dict-to-dataclass conversion
        config = PRAgentConfig()

        # Update git server configs
        if "github" in data:
            github_data = data["github"]
            config.github = GitServerConfig(
                name="github",
                api_url=github_data.get("api_url", config.github.api_url),
                token=github_data.get("token"),
                enabled=github_data.get("enabled", True),
            )

        # Update analyzer config
        if "analyzers" in data:
            analyzer_data = data["analyzers"]
            for key, value in analyzer_data.items():
                if hasattr(config.analyzers, key):
                    setattr(config.analyzers, key, value)

        # Update review config
        if "review" in data:
            review_data = data["review"]
            for key, value in review_data.items():
                if hasattr(config.review, key):
                    setattr(config.review, key, value)

        return config

    def _find_env_file(self) -> Optional[str]:
        """Find .env file in current directory or parent directories."""
        current = Path.cwd()

        while current != current.parent:
            env_file = current / ".env"
            if env_file.exists():
                return str(env_file)
            current = current.parent

        return None

    def save_config(self, output_file: str) -> None:
        """Save current configuration to a YAML file."""
        config_dict = self._config_to_dict(self.config)

        with open(output_file, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)

    def _config_to_dict(self, config: PRAgentConfig) -> Dict[str, Any]:
        """Convert PRAgentConfig to dictionary for serialization."""
        return {
            "github": {
                "api_url": config.github.api_url,
                "enabled": config.github.enabled,
            },
            "gitlab": {
                "api_url": config.gitlab.api_url,
                "enabled": config.gitlab.enabled,
            },
            "bitbucket": {
                "api_url": config.bitbucket.api_url,
                "enabled": config.bitbucket.enabled,
            },
            "analyzers": {
                "flake8_enabled": config.analyzers.flake8_enabled,
                "flake8_max_line_length": config.analyzers.flake8_max_line_length,
                "flake8_ignore": config.analyzers.flake8_ignore,
                "bandit_enabled": config.analyzers.bandit_enabled,
                "eslint_enabled": config.analyzers.eslint_enabled,
                "mypy_enabled": config.analyzers.mypy_enabled,
                "ai_enabled": config.analyzers.ai_enabled,
                "ai_model": config.analyzers.ai_model,
                "ai_temperature": config.analyzers.ai_temperature,
                "ai_max_tokens": config.analyzers.ai_max_tokens,
                "security_patterns_enabled": config.analyzers.security_patterns_enabled,
            },
            "review": {
                "post_summary": config.review.post_summary,
                "post_inline_comments": config.review.post_inline_comments,
                "max_inline_comments": config.review.max_inline_comments,
                "max_diff_size": config.review.max_diff_size,
                "min_confidence_threshold": config.review.min_confidence_threshold,
                "severity_filter": config.review.severity_filter,
            },
            "debug": config.debug,
            "verbose": config.verbose,
        }


if __name__ == "__main__":
    # Example usage
    config_manager = ConfigManager()
    config = config_manager.get_config()

    print("Configuration loaded:")
    print(f"AI enabled: {config.analyzers.ai_enabled}")
    print(f"AI model: {config.analyzers.ai_model}")
    print(f"GitHub API URL: {config.github.api_url}")
    print(f"Post inline comments: {config.review.post_inline_comments}")

    # Validate configuration
    errors = config_manager.validate_config()
    if errors:
        print("\nConfiguration errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✅ Configuration is valid")
