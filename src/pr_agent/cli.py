"""
Command-line interface for the PR Review Agent.

This module provides the main entry point for running PR reviews
from the command line with various configuration options.
"""

import argparse
import sys
import os
from typing import Optional, Dict, Any
from pathlib import Path

# Add the src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pr_agent.config import ConfigManager
from pr_agent.adapters.github_adapter import GitHubAdapter
from pr_agent.adapters.gitlab_adapter import GitLabAdapter
from pr_agent.diff_parser import DiffParser
from pr_agent.analyzers.static_analyzer import StaticAnalyzer
from pr_agent.analyzers.ai_analyzer import AIAnalyzer
from pr_agent.reporter import Reporter


class PRReviewCLI:
    """Command-line interface for the PR Review Agent."""

    def __init__(self):
        """Initialize the CLI."""
        self.config_manager = None
        self.config = None

    def create_parser(self) -> argparse.ArgumentParser:
        """Create the command-line argument parser."""
        parser = argparse.ArgumentParser(
            description="AI-powered PR Review Agent",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Review a GitHub PR
  python -m pr_agent.cli --provider github --owner myorg --repo myrepo --pr 123

  # Review with custom settings
  python -m pr_agent.cli --provider github --owner myorg --repo myrepo --pr 123 \\
    --no-inline --ai-model gpt-4 --max-comments 10

  # Validate configuration
  python -m pr_agent.cli --validate-config

  # Generate sample config
  python -m pr_agent.cli --generate-config
            """,
        )

        # Required arguments for PR review
        pr_group = parser.add_argument_group("PR Review Arguments")
        pr_group.add_argument(
            "--provider",
            choices=["github", "gitlab", "bitbucket"],
            help="Git server provider",
        )
        pr_group.add_argument("--owner", help="Repository owner/organization")
        pr_group.add_argument("--repo", help="Repository name")
        pr_group.add_argument("--pr", type=int, help="Pull request number")

        # Configuration
        config_group = parser.add_argument_group("Configuration")
        config_group.add_argument(
            "--config", help="Path to configuration file (YAML format)"
        )
        config_group.add_argument(
            "--validate-config",
            action="store_true",
            help="Validate configuration and exit",
        )
        config_group.add_argument(
            "--generate-config", help="Generate sample configuration file and exit"
        )

        # Analysis options
        analysis_group = parser.add_argument_group("Analysis Options")
        analysis_group.add_argument(
            "--no-ai", action="store_true", help="Disable AI-powered analysis"
        )
        analysis_group.add_argument(
            "--no-static", action="store_true", help="Disable static analysis"
        )
        analysis_group.add_argument(
            "--ai-model",
            default="gemini-1.5-flash",
            help="Gemini model to use for AI analysis (default: gemini-1.5-flash)",
        )
        analysis_group.add_argument(
            "--confidence-threshold",
            type=float,
            metavar="FLOAT",
            help="Minimum confidence threshold for AI feedback (0.0-1.0)",
        )

        # Review options
        review_group = parser.add_argument_group("Review Options")
        review_group.add_argument(
            "--no-inline",
            action="store_true",
            help="Disable inline comments, only post summary",
        )
        review_group.add_argument(
            "--no-summary",
            action="store_true",
            help="Disable summary comment, only post inline comments",
        )
        review_group.add_argument(
            "--max-comments",
            type=int,
            metavar="N",
            help="Maximum number of inline comments to post",
        )
        review_group.add_argument(
            "--dry-run",
            action="store_true",
            help="Perform analysis but don't post comments (print to stdout)",
        )

        # Output options
        output_group = parser.add_argument_group("Output Options")
        output_group.add_argument(
            "--verbose", "-v", action="store_true", help="Enable verbose output"
        )
        output_group.add_argument(
            "--debug", action="store_true", help="Enable debug output"
        )
        output_group.add_argument(
            "--json", action="store_true", help="Output results in JSON format"
        )
        output_group.add_argument("--output", help="Save results to file")

        return parser

    def run(self, args: Optional[list] = None) -> int:
        """
        Run the PR review agent.

        Args:
            args: Command-line arguments (defaults to sys.argv)

        Returns:
            Exit code (0 for success, 1 for error)
        """
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)

        try:
            # Handle special commands first
            if parsed_args.validate_config:
                return self._validate_config(parsed_args)

            if parsed_args.generate_config:
                return self._generate_config(parsed_args.generate_config)

            # Load configuration
            self.config_manager = ConfigManager(
                config_file=parsed_args.config, load_env=True
            )
            self.config = self.config_manager.get_config()

            # Update config from command line args
            args_dict = vars(parsed_args)
            self.config_manager.update_from_args(args_dict)

            # Validate configuration
            errors = self.config_manager.validate_config()
            if errors:
                print("Configuration errors:")
                for error in errors:
                    print(f"  - {error}")
                return 1

            # Check required arguments for PR review
            if not all(
                [
                    parsed_args.provider,
                    parsed_args.owner,
                    parsed_args.repo,
                    parsed_args.pr,
                ]
            ):
                parser.print_help()
                print(
                    "\nError: --provider, --owner, --repo, and --pr are required for PR review"
                )
                return 1

            # Perform PR review
            return self._review_pr(parsed_args)

        except KeyboardInterrupt:
            print("\n🛑 Review cancelled by user")
            return 1
        except Exception as e:
            if parsed_args.debug:
                import traceback

                traceback.print_exc()
            else:
                print(f"Error: {e}")
            return 1

    def _review_pr(self, args: argparse.Namespace) -> int:
        """Perform the actual PR review."""
        if args.verbose:
            print(f"Starting PR review for {args.owner}/{args.repo}#{args.pr}")

        # Initialize adapter
        adapter = self._create_adapter(args.provider)
        if not adapter:
            print(f"❌ Unsupported provider: {args.provider}")
            return 1

        # Validate credentials
        if not adapter.validate_credentials():
            print(f"❌ Invalid credentials for {args.provider}")
            return 1

        if args.verbose:
            print(f"✅ Connected to {args.provider}")

        try:
            # Get PR information
            pr_info = adapter.get_pr_info(args.owner, args.repo, args.pr)
            if args.verbose:
                print(f"📋 PR: {pr_info.title}")
                print(f"📝 Author: {pr_info.author}")
                print(f"🔀 {pr_info.source_branch} → {pr_info.target_branch}")

            # Get PR diff
            diff_text = adapter.get_pr_diff(args.owner, args.repo, args.pr)
            if not diff_text.strip():
                print("⚠️  No changes found in PR")
                return 0

            # Parse diff
            diff_parser = DiffParser(diff_text)
            stats = diff_parser.get_statistics()

            if args.verbose:
                print(
                    f"📊 Changes: {stats['files']} files, +{stats['additions']} -{stats['deletions']}"
                )

            # Check diff size
            if (
                stats["additions"] + stats["deletions"]
                > self.config.review.max_diff_size
            ):
                print(
                    f"⚠️  Diff too large ({stats['additions'] + stats['deletions']} changes, max {self.config.review.max_diff_size})"
                )
                print("Consider reviewing smaller PRs or increasing max_diff_size")
                return 0

            # Run static analysis
            static_issues = []
            if not args.no_static and self.config.analyzers.flake8_enabled:
                if args.verbose:
                    print("🔍 Running static analysis...")

                static_analyzer = StaticAnalyzer()
                files = diff_parser.get_files()

                # For now, analyze diff content directly
                # In a full implementation, you'd clone the repo and analyze files
                for file_path in files:
                    file_analysis = diff_parser.get_file_analysis(file_path)
                    if file_analysis:
                        # Extract added content for analysis
                        added_content = "\n".join(
                            [
                                change.line_content
                                for change in file_analysis.line_changes
                                if change.change_type == "added"
                            ]
                        )
                        if added_content:
                            file_type = Path(file_path).suffix
                            file_issues = static_analyzer.analyze_diff_content(
                                added_content, file_path, file_type
                            )
                            static_issues.extend(file_issues)

                if args.verbose:
                    print(f"📝 Found {len(static_issues)} static analysis issues")

            # Run AI analysis
            ai_feedback = []
            quality_score = None
            ai_summary = None
            if not args.no_ai and self.config.analyzers.ai_enabled:
                if args.verbose:
                    print("Running AI analysis...")

                try:
                    ai_analyzer = AIAnalyzer(
                        model=self.config.analyzers.ai_model,
                        api_key=self.config.gemini_api_key,
                    )

                    pr_metadata = {
                        "title": pr_info.title,
                        "description": pr_info.description,
                        "author": pr_info.author,
                    }

                    ai_feedback, quality_score, ai_summary = ai_analyzer.analyze_diff(
                        diff_text, pr_metadata
                    )

                    # Filter by confidence threshold
                    if self.config.review.min_confidence_threshold > 0:
                        ai_feedback = [
                            feedback
                            for feedback in ai_feedback
                            if feedback.confidence
                            >= self.config.review.min_confidence_threshold
                        ]

                    if args.verbose:
                        print(f"Generated {len(ai_feedback)} AI feedback items")
                        if quality_score:
                            print(f"Overall quality score: {quality_score.overall}/100")

                except Exception as e:
                    print(f"AI analysis failed: {e}")
                    if args.debug:
                        import traceback

                        traceback.print_exc()

            # Generate and post review
            if args.dry_run:
                return self._print_results(static_issues, ai_feedback, args)
            else:
                return self._post_review(
                    adapter,
                    args,
                    static_issues,
                    ai_feedback,
                    pr_info,
                    quality_score,
                    ai_summary,
                )

        except Exception as e:
            print(f"Review failed: {e}")
            if args.debug:
                import traceback

                traceback.print_exc()
            return 1

    def _create_adapter(self, provider: str):
        """Create appropriate adapter for the git provider."""
        provider = provider.lower()

        if provider == "github":
            git_config = self.config_manager.get_git_server_config("github")
            return GitHubAdapter(token=git_config.token, api_url=git_config.api_url)
        elif provider == "gitlab":
            git_config = self.config_manager.get_git_server_config("gitlab")
            return GitLabAdapter(token=git_config.token, api_url=git_config.api_url)
        # Add bitbucket when implemented

        return None

    def _post_review(
        self,
        adapter,
        args,
        static_issues,
        ai_feedback,
        pr_info,
        quality_score=None,
        ai_summary=None,
    ) -> int:
        """Post the review to the PR."""
        if args.verbose:
            print("Posting review...")

        reporter = Reporter(adapter)

        pr_metadata = {
            "title": pr_info.title,
            "description": pr_info.description,
            "author": pr_info.author,
        }

        results = reporter.post_review(
            owner=args.owner,
            repo=args.repo,
            pr_number=args.pr,
            static_issues=static_issues,
            ai_feedback=ai_feedback,
            pr_info=pr_metadata,
            post_inline=not args.no_inline and self.config.review.post_inline_comments,
            post_summary=not args.no_summary and self.config.review.post_summary,
            quality_score=quality_score,
            ai_summary=ai_summary,
        )

        if results["summary_posted"]:
            print("Summary comment posted")

        if results["inline_comments"] > 0:
            print(f"{results['inline_comments']} inline comments posted")

        if results["errors"]:
            print("Some errors occurred:")
            for error in results["errors"]:
                print(f"  - {error}")
            return 1

        print("🎉 Review completed successfully!")
        return 0

    def _print_results(self, static_issues, ai_feedback, args) -> int:
        """Print results to stdout (dry run mode)."""
        print("🔍 DRY RUN - Review Results")
        print("=" * 50)

        if static_issues:
            print(f"\n📝 Static Analysis Issues ({len(static_issues)}):")
            for issue in static_issues:
                print(
                    f"  {issue.severity.upper()}: {issue.file_path}:{issue.line_number}"
                )
                print(f"    {issue.message}")
                if issue.rule_id:
                    print(f"    Rule: {issue.rule_id}")
                print()

        if ai_feedback:
            print(f"\n🤖 AI Feedback ({len(ai_feedback)}):")
            for feedback in ai_feedback:
                location = (
                    f"{feedback.file_path}:{feedback.line_number}"
                    if feedback.file_path and feedback.line_number
                    else "General"
                )
                print(f"  {feedback.severity.upper()}: {location}")
                print(f"    {feedback.message}")
                if feedback.suggestion:
                    print(f"    Suggestion: {feedback.suggestion}")
                print(f"    Confidence: {feedback.confidence:.0%}")
                print()

        if not static_issues and not ai_feedback:
            print("\n✅ No issues found!")

        return 0

    def _validate_config(self, args) -> int:
        """Validate configuration and print results."""
        try:
            config_manager = ConfigManager(config_file=args.config)
            errors = config_manager.validate_config()

            if errors:
                print("❌ Configuration validation failed:")
                for error in errors:
                    print(f"  - {error}")
                return 1
            else:
                print("Configuration is valid")
                return 0

        except Exception as e:
            print(f"❌ Failed to validate configuration: {e}")
            return 1

    def _generate_config(self, output_file: str) -> int:
        """Generate a sample configuration file."""
        try:
            config_manager = ConfigManager(load_env=False)
            config_manager.save_config(output_file)
            print(f"✅ Sample configuration saved to {output_file}")
            print("Edit the file with your settings and API keys.")
            return 0

        except Exception as e:
            print(f"❌ Failed to generate configuration: {e}")
            return 1


def main():
    """Main entry point."""
    cli = PRReviewCLI()
    exit_code = cli.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
