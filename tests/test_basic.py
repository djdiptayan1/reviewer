"""
Basic tests for the PR Review Agent.

This module contains simple tests to verify the core functionality
of the PR review agent components.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from pr_agent.diff_parser import DiffParser
from pr_agent.analyzers.static_analyzer import StaticAnalyzer
from pr_agent.config import ConfigManager


def test_diff_parser():
    """Test basic diff parsing functionality."""
    sample_diff = """diff --git a/example.py b/example.py
index 1234567..abcdefg 100644
--- a/example.py
+++ b/example.py
@@ -1,4 +1,6 @@
 def hello_world():
-    print("Hello")
+    print("Hello, World!")
+    return "greeting"
+
 def main():
     hello_world()
"""

    parser = DiffParser(sample_diff)

    # Test basic parsing
    files = parser.get_files()
    assert len(files) == 1
    assert files[0] == "example.py"

    # Test statistics
    stats = parser.get_statistics()
    assert stats["files"] == 1
    assert stats["additions"] == 2
    assert stats["deletions"] == 1

    # Test added lines
    added_lines = parser.get_added_lines_with_positions()
    assert "example.py" in added_lines
    assert len(added_lines["example.py"]) == 2


def test_static_analyzer():
    """Test static analyzer with sample code."""
    analyzer = StaticAnalyzer()

    # Sample Python code with issues
    sample_code = """
def example_function():
    password = "hardcoded123"  # Security issue
    eval("print('hello')")      # Security issue
    unused_variable = 42        # Potential issue
    return password
"""

    issues = analyzer.analyze_diff_content(sample_code, "example.py", ".py")

    # Should find some security issues at minimum
    assert len(issues) > 0

    # Check for security patterns
    security_issues = [issue for issue in issues if issue.tool == "security_patterns"]
    assert len(security_issues) > 0


def test_config_manager():
    """Test configuration management."""
    config_manager = ConfigManager(load_env=False)
    config = config_manager.get_config()

    # Test default values
    assert config.analyzers.ai_enabled == True
    assert config.analyzers.ai_model == "gpt-4o-mini"
    assert config.review.post_summary == True
    assert config.review.post_inline_comments == True

    # Test validation
    errors = config_manager.validate_config()
    # Should have errors since no API keys are set
    assert len(errors) > 0


def test_empty_diff():
    """Test handling of empty diff."""
    parser = DiffParser("")

    files = parser.get_files()
    assert len(files) == 0

    stats = parser.get_statistics()
    assert stats["files"] == 0
    assert stats["additions"] == 0
    assert stats["deletions"] == 0


if __name__ == "__main__":
    print("Running basic tests...")

    try:
        test_diff_parser()
        print("✅ Diff parser test passed")

        test_static_analyzer()
        print("✅ Static analyzer test passed")

        test_config_manager()
        print("✅ Config manager test passed")

        test_empty_diff()
        print("✅ Empty diff test passed")

        print("\n🎉 All tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
