#!/usr/bin/env python3
"""
Example script demonstrating how to use the PR Review Agent programmatically.

This script shows how to integrate the PR Review Agent into your own tools
or workflows without using the command-line interface.
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pr_agent.config import ConfigManager
from pr_agent.adapters.github_adapter import GitHubAdapter
from pr_agent.diff_parser import DiffParser
from pr_agent.analyzers.static_analyzer import StaticAnalyzer
from pr_agent.analyzers.ai_analyzer import AIAnalyzer
from pr_agent.reporter import Reporter


def review_pr_example():
    """Example of reviewing a PR programmatically."""

    # Configuration
    owner = "your-org"
    repo = "your-repo"
    pr_number = 123

    print(f"🚀 Starting review of {owner}/{repo}#{pr_number}")

    try:
        # 1. Load configuration
        config_manager = ConfigManager()
        config = config_manager.get_config()

        # Validate configuration
        errors = config_manager.validate_config()
        if errors:
            print("❌ Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return False

        print("✅ Configuration loaded")

        # 2. Initialize GitHub adapter
        github_config = config_manager.get_git_server_config("github")
        adapter = GitHubAdapter(
            token=github_config.token, api_url=github_config.api_url
        )

        # Validate credentials
        if not adapter.validate_credentials():
            print("❌ Invalid GitHub credentials")
            return False

        print("✅ Connected to GitHub")

        # 3. Get PR information
        pr_info = adapter.get_pr_info(owner, repo, pr_number)
        print(f"📋 PR: {pr_info.title}")
        print(f"📝 Author: {pr_info.author}")
        print(f"🔀 {pr_info.source_branch} → {pr_info.target_branch}")

        # 4. Get and parse diff
        diff_text = adapter.get_pr_diff(owner, repo, pr_number)
        if not diff_text.strip():
            print("⚠️  No changes found in PR")
            return True

        parser = DiffParser(diff_text)
        stats = parser.get_statistics()
        print(
            f"📊 Changes: {stats['files']} files, +{stats['additions']} -{stats['deletions']}"
        )

        # 5. Run static analysis
        print("🔍 Running static analysis...")
        static_analyzer = StaticAnalyzer()
        static_issues = []

        for file_path in parser.get_files():
            file_analysis = parser.get_file_analysis(file_path)
            if file_analysis:
                # Get added content for analysis
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

        print(f"📝 Found {len(static_issues)} static analysis issues")

        # 6. Run AI analysis (if configured)
        ai_feedback = []
        if config.analyzers.ai_enabled and config.gemini_api_key:
            print("🤖 Running AI analysis...")

            try:
                ai_analyzer = AIAnalyzer(
                    api_key=config.gemini_api_key, model=config.analyzers.ai_model
                )

                pr_metadata = {
                    "title": pr_info.title,
                    "description": pr_info.description,
                    "author": pr_info.author,
                }

                ai_feedback = ai_analyzer.analyze_diff(diff_text, pr_metadata)
                print(f"🧠 Generated {len(ai_feedback)} AI feedback items")

            except Exception as e:
                print(f"⚠️  AI analysis failed: {e}")

        # 7. Generate and post review
        print("📤 Posting review...")
        reporter = Reporter(adapter)

        pr_metadata = {
            "title": pr_info.title,
            "description": pr_info.description,
            "author": pr_info.author,
        }

        results = reporter.post_review(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            static_issues=static_issues,
            ai_feedback=ai_feedback,
            pr_info=pr_metadata,
            post_inline=config.review.post_inline_comments,
            post_summary=config.review.post_summary,
        )

        # 8. Report results
        if results["summary_posted"]:
            print("✅ Summary comment posted")

        if results["inline_comments"] > 0:
            print(f"✅ {results['inline_comments']} inline comments posted")

        if results["errors"]:
            print("⚠️  Some errors occurred:")
            for error in results["errors"]:
                print(f"  - {error}")
            return False

        print("🎉 Review completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Review failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def dry_run_example():
    """Example of analyzing a PR without posting comments."""

    print("🔍 DRY RUN - Analyzing PR without posting...")

    # Sample diff for demonstration
    sample_diff = """diff --git a/example.py b/example.py
index 1234567..abcdefg 100644
--- a/example.py
+++ b/example.py
@@ -1,5 +1,8 @@
 def calculate_average(numbers):
-    return sum(numbers) / len(numbers)
+    if len(numbers) == 0:
+        return 0
+    total = sum(numbers)
+    return total / len(numbers)
 
 def main():
-    result = calculate_average([1, 2, 3])
+    result = calculate_average([1, 2, 3, 4, 5])
     print(f"Average: {result}")
"""

    try:
        # Parse diff
        parser = DiffParser(sample_diff)
        stats = parser.get_statistics()
        print(
            f"📊 Changes: {stats['files']} files, +{stats['additions']} -{stats['deletions']}"
        )

        # Run static analysis on added content
        static_analyzer = StaticAnalyzer()
        static_issues = []

        for file_path in parser.get_files():
            file_analysis = parser.get_file_analysis(file_path)
            if file_analysis:
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

        print(f"📝 Found {len(static_issues)} static analysis issues")

        # Display results
        if static_issues:
            print("\nStatic Analysis Issues:")
            for issue in static_issues:
                print(
                    f"  {issue.severity.upper()}: {issue.file_path}:{issue.line_number}"
                )
                print(f"    {issue.message}")
        else:
            print("\n✅ No static analysis issues found!")

        return True

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return False


def main():
    """Main function with examples."""
    print("PR Review Agent - Programmatic Examples")
    print("=" * 50)

    # Check if we have the required environment variables for full example
    if os.environ.get("GITHUB_TOKEN") and os.environ.get("GEMINI_API_KEY"):
        print("\n1. Full PR Review Example (requires real PR)")
        print("   Set owner, repo, and pr_number in the script to test")
        # Uncomment the next line and set real values to test
        # review_pr_example()
    else:
        print("\n1. Skipping full PR review (missing GITHUB_TOKEN or GEMINI_API_KEY)")

    print("\n2. Dry Run Example (no API calls)")
    if dry_run_example():
        print("✅ Dry run completed successfully")
    else:
        print("❌ Dry run failed")

    print("\n3. Configuration Example")
    try:
        config_manager = ConfigManager(load_env=False)
        config = config_manager.get_config()
        print(f"✅ Default AI model: {config.analyzers.ai_model}")
        print(f"✅ Max diff size: {config.review.max_diff_size}")
        print(f"✅ Inline comments enabled: {config.review.post_inline_comments}")
    except Exception as e:
        print(f"❌ Configuration failed: {e}")


if __name__ == "__main__":
    main()
