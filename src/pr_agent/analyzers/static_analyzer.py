"""
Static code analyzer for running linters and security scanners.

This module provides functionality to run various static analysis tools
on changed files and collect issues for review.
"""

import os
import subprocess
import tempfile
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class AnalysisIssue:
    """Represents a detailed static analysis issue."""

    tool: str
    file_path: str
    line_number: int
    column: Optional[int]
    severity: str  # critical, error, warning, info
    code: str
    message: str
    rule_id: Optional[str] = None
    description: Optional[str] = None  # Detailed explanation
    suggestion: Optional[str] = None  # How to fix
    category: str = "style"  # style, security, performance, etc.
    documentation_url: Optional[str] = None  # Link to rule docs


class StaticAnalyzer:
    """Static code analyzer that runs multiple tools."""

    def __init__(self, tools_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the static analyzer.

        Args:
            tools_config: Configuration for analysis tools
        """
        self.tools_config = tools_config or self._get_default_config()
        self.temp_dir = None

    def analyze_files(self, files: List[str], repo_path: str) -> List[AnalysisIssue]:
        """
        Analyze a list of files using configured tools.

        Args:
            files: List of file paths to analyze
            repo_path: Root path of the repository

        Returns:
            List of analysis issues found
        """
        all_issues = []

        for file_path in files:
            full_path = os.path.join(repo_path, file_path)
            if not os.path.exists(full_path):
                continue

            file_ext = self._get_file_extension(file_path)

            # Run appropriate analyzers based on file type
            if file_ext == ".py":
                all_issues.extend(self._analyze_python_file(full_path, file_path))
            elif file_ext in [".js", ".ts", ".jsx", ".tsx"]:
                all_issues.extend(self._analyze_javascript_file(full_path, file_path))
            elif file_ext in [".java"]:
                all_issues.extend(self._analyze_java_file(full_path, file_path))

            # Run security analyzers
            all_issues.extend(self._run_security_analysis(full_path, file_path))

        return all_issues

    def analyze_diff_content(
        self, file_content: str, file_path: str, file_type: str
    ) -> List[AnalysisIssue]:
        """
        Analyze file content directly without writing to disk.

        Args:
            file_content: Content of the file to analyze
            file_path: Virtual path of the file
            file_type: Type/extension of the file

        Returns:
            List of analysis issues found
        """
        issues = []

        # Create temporary file for analysis
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=file_type, delete=False
        ) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            if file_type == ".py":
                issues = self._analyze_python_file(temp_file_path, file_path)
            elif file_type in [".js", ".ts", ".jsx", ".tsx"]:
                issues = self._analyze_javascript_file(temp_file_path, file_path)
        finally:
            os.unlink(temp_file_path)

        return issues

    def _analyze_python_file(
        self, full_path: str, relative_path: str
    ) -> List[AnalysisIssue]:
        """Analyze Python file using flake8 and other Python tools."""
        issues = []

        # Run flake8
        if self.tools_config.get("flake8", {}).get("enabled", True):
            issues.extend(self._run_flake8(full_path, relative_path))

        # Run bandit for security issues
        if self.tools_config.get("bandit", {}).get("enabled", True):
            issues.extend(self._run_bandit(full_path, relative_path))

        # Run mypy for type checking (optional)
        if self.tools_config.get("mypy", {}).get("enabled", False):
            issues.extend(self._run_mypy(full_path, relative_path))

        return issues

    def _analyze_javascript_file(
        self, full_path: str, relative_path: str
    ) -> List[AnalysisIssue]:
        """Analyze JavaScript/TypeScript file using ESLint."""
        issues = []

        if self.tools_config.get("eslint", {}).get("enabled", True):
            issues.extend(self._run_eslint(full_path, relative_path))

        return issues

    def _analyze_java_file(
        self, full_path: str, relative_path: str
    ) -> List[AnalysisIssue]:
        """Analyze Java file using available tools."""
        issues = []

        # Could add SpotBugs, PMD, or other Java static analyzers
        # For now, just basic analysis

        return issues

    def _run_flake8(self, file_path: str, relative_path: str) -> List[AnalysisIssue]:
        """Run flake8 on a Python file."""
        issues = []

        try:
            cmd = [
                "flake8",
                "--format=%(path)s:%(row)d:%(col)d:%(code)s:%(text)s",
                file_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    issue = self._parse_flake8_output(line, relative_path)
                    if issue:
                        issues.append(issue)

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            # flake8 not installed or timed out
            pass

        return issues

    def _run_bandit(self, file_path: str, relative_path: str) -> List[AnalysisIssue]:
        """Run bandit security scanner on a Python file."""
        issues = []

        try:
            cmd = ["bandit", "-f", "json", file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.stdout:
                data = json.loads(result.stdout)
                for result_item in data.get("results", []):
                    issue = AnalysisIssue(
                        tool="bandit",
                        file_path=relative_path,
                        line_number=result_item["line_number"],
                        column=None,
                        severity=result_item["issue_severity"].lower(),
                        code=result_item["test_id"],
                        message=result_item["issue_text"],
                        rule_id=result_item["test_name"],
                    )
                    issues.append(issue)

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            # bandit not installed, timed out, or output parsing failed
            pass

        return issues

    def _run_mypy(self, file_path: str, relative_path: str) -> List[AnalysisIssue]:
        """Run mypy type checker on a Python file."""
        issues = []

        try:
            cmd = ["mypy", "--show-column-numbers", "--no-error-summary", file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            for line in result.stdout.strip().split("\n"):
                if line.strip() and ":" in line:
                    issue = self._parse_mypy_output(line, relative_path)
                    if issue:
                        issues.append(issue)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # mypy not installed or timed out
            pass

        return issues

    def _run_eslint(self, file_path: str, relative_path: str) -> List[AnalysisIssue]:
        """Run ESLint on a JavaScript/TypeScript file."""
        issues = []

        try:
            cmd = ["eslint", "--format", "json", file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.stdout:
                data = json.loads(result.stdout)
                for file_result in data:
                    for message in file_result.get("messages", []):
                        severity_map = {1: "warning", 2: "error"}
                        issue = AnalysisIssue(
                            tool="eslint",
                            file_path=relative_path,
                            line_number=message["line"],
                            column=message["column"],
                            severity=severity_map.get(message["severity"], "info"),
                            code=message.get("ruleId", ""),
                            message=message["message"],
                            rule_id=message.get("ruleId"),
                        )
                        issues.append(issue)

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            # eslint not installed, timed out, or output parsing failed
            pass

        return issues

    def _run_security_analysis(
        self, file_path: str, relative_path: str
    ) -> List[AnalysisIssue]:
        """Run security-focused analysis."""
        issues = []

        # Basic pattern-based security checks
        security_patterns = [
            (
                r'password\s*=\s*["\'][^"\']*["\']',
                "hardcoded_password",
                "Potential hardcoded password",
            ),
            (
                r'api_key\s*=\s*["\'][^"\']*["\']',
                "hardcoded_api_key",
                "Potential hardcoded API key",
            ),
            (r"eval\s*\(", "eval_usage", "Use of eval() can be dangerous"),
            (r"exec\s*\(", "exec_usage", "Use of exec() can be dangerous"),
            (
                r"pickle\.loads?\s*\(",
                "pickle_usage",
                "Pickle can execute arbitrary code",
            ),
        ]

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    for pattern, code, message in security_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            issue = AnalysisIssue(
                                tool="security_patterns",
                                file_path=relative_path,
                                line_number=line_num,
                                column=None,
                                severity="warning",
                                code=code,
                                message=message,
                            )
                            issues.append(issue)

        except Exception:
            pass

        return issues

    def _parse_flake8_output(
        self, line: str, relative_path: str
    ) -> Optional[AnalysisIssue]:
        """Parse flake8 output line into enhanced AnalysisIssue."""
        try:
            # Format: path:line:col:code:message
            parts = line.split(":", 4)
            if len(parts) >= 5:
                code = parts[3]
                message = parts[4].strip()

                # Enhanced severity mapping
                severity_map = {
                    "E": "error",
                    "W": "warning",
                    "F": "error",
                    "C": "warning",
                    "N": "info",
                }
                severity = severity_map.get(code[0], "info")

                # Get detailed information about the rule
                description, suggestion, category, doc_url = (
                    self._get_flake8_rule_details(code)
                )

                return AnalysisIssue(
                    tool="flake8",
                    file_path=relative_path,
                    line_number=int(parts[1]),
                    column=int(parts[2]),
                    severity=severity,
                    code=code,
                    message=message,
                    rule_id=code,
                    description=description,
                    suggestion=suggestion,
                    category=category,
                    documentation_url=doc_url,
                )
        except (ValueError, IndexError):
            pass

        return None

    def _get_flake8_rule_details(self, code: str) -> Tuple[str, str, str, str]:
        """Get detailed information about flake8 rules."""
        rule_info = {
            # Indentation errors (E1xx)
            "E101": (
                "Indentation contains mixed spaces and tabs",
                "Use either spaces or tabs consistently for indentation, not both",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            "E111": (
                "Indentation is not a multiple of four",
                "Use 4 spaces per indentation level as per PEP 8",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            "E112": (
                "Expected an indented block",
                "Add proper indentation after colons (:) in control structures",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            # Whitespace errors (E2xx)
            "E201": (
                "Whitespace after '('",
                "Remove extra spaces after opening parentheses, brackets, or braces",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            "E202": (
                "Whitespace before ')'",
                "Remove extra spaces before closing parentheses, brackets, or braces",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            "E203": (
                "Whitespace before ':'",
                "Remove spaces before colons in slices and dictionary literals",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            "E211": (
                "Whitespace before '('",
                "Remove spaces before opening parentheses in function calls",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            # Line length (E501)
            "E501": (
                "Line too long",
                "Break long lines using parentheses, backslashes, or refactor into shorter statements",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            # Import errors (E4xx)
            "E401": (
                "Multiple imports on one line",
                "Import each module on a separate line: 'import os\\nimport sys' instead of 'import os, sys'",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            "E402": (
                "Module level import not at top of file",
                "Move all imports to the top of the file, after module docstrings",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            # Runtime errors (F8xx)
            "F401": (
                "Module imported but unused",
                "Remove unused import or use it in the code",
                "maintainability",
                "https://flake8.pycqa.org/en/latest/user/error-codes.html",
            ),
            "F402": (
                "Import module from line shadowed by loop variable",
                "Rename the loop variable to avoid shadowing the import",
                "maintainability",
                "https://flake8.pycqa.org/en/latest/user/error-codes.html",
            ),
            "F403": (
                "'from module import *' used; unable to detect undefined names",
                "Use explicit imports instead of 'import *' for better code clarity",
                "maintainability",
                "https://flake8.pycqa.org/en/latest/user/error-codes.html",
            ),
            "F811": (
                "Redefinition of unused name from line N",
                "Remove the previous definition or rename one of the variables",
                "maintainability",
                "https://flake8.pycqa.org/en/latest/user/error-codes.html",
            ),
            "F821": (
                "Undefined name",
                "Define the variable before using it or check for typos",
                "error",
                "https://flake8.pycqa.org/en/latest/user/error-codes.html",
            ),
            "F822": (
                "Undefined name in __all__",
                "Ensure all names in __all__ are defined in the module",
                "error",
                "https://flake8.pycqa.org/en/latest/user/error-codes.html",
            ),
            "F831": (
                "Duplicate argument name in function definition",
                "Remove the duplicate parameter or rename one of them",
                "error",
                "https://flake8.pycqa.org/en/latest/user/error-codes.html",
            ),
            "F841": (
                "Local variable is assigned to but never used",
                "Remove the unused variable or prefix it with underscore if intentional",
                "maintainability",
                "https://flake8.pycqa.org/en/latest/user/error-codes.html",
            ),
            # Warnings (W2xx, W3xx, W5xx, W6xx)
            "W291": (
                "Trailing whitespace",
                "Remove trailing spaces and tabs at the end of lines",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            "W292": (
                "No newline at end of file",
                "Add a single newline character at the end of the file",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            "W293": (
                "Blank line contains whitespace",
                "Remove any spaces or tabs from blank lines",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
            "W391": (
                "Blank line at end of file",
                "Remove extra blank lines at the end of the file",
                "style",
                "https://pep8.readthedocs.io/en/release-1.7.x/intro.html#error-codes",
            ),
        }

        if code in rule_info:
            return rule_info[code]

        # Default for unknown codes
        category = (
            "style"
            if code.startswith(("E", "W"))
            else "error" if code.startswith("F") else "info"
        )
        return (
            "Static analysis issue detected",
            "Review the code and follow Python style guidelines",
            category,
            "https://flake8.pycqa.org/en/latest/user/error-codes.html",
        )

    def _parse_mypy_output(
        self, line: str, relative_path: str
    ) -> Optional[AnalysisIssue]:
        """Parse mypy output line into AnalysisIssue."""
        try:
            # Format: path:line:col: level: message
            match = re.match(r"^[^:]+:(\d+):(\d+):\s*(\w+):\s*(.+)$", line)
            if match:
                line_num, col, level, message = match.groups()
                severity = "error" if level == "error" else "warning"

                return AnalysisIssue(
                    tool="mypy",
                    file_path=relative_path,
                    line_number=int(line_num),
                    column=int(col),
                    severity=severity,
                    code="mypy",
                    message=message.strip(),
                )
        except ValueError:
            pass

        return None

    def _get_file_extension(self, file_path: str) -> str:
        """Get file extension from path."""
        return Path(file_path).suffix.lower()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for analysis tools."""
        return {
            "flake8": {
                "enabled": True,
                "max_line_length": 88,
                "ignore": ["E203", "W503"],
            },
            "bandit": {"enabled": True, "confidence_level": "medium"},
            "mypy": {
                "enabled": False,  # Can be slow and require configuration
                "strict": False,
            },
            "eslint": {"enabled": True, "config_file": None},
            "security_patterns": {"enabled": True},
        }

    def get_issue_summary(self, issues: List[AnalysisIssue]) -> Dict[str, Any]:
        """Get summary statistics for analysis issues."""
        if not issues:
            return {"total": 0, "by_severity": {}, "by_tool": {}}

        by_severity = {}
        by_tool = {}

        for issue in issues:
            # Count by severity
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1

            # Count by tool
            by_tool[issue.tool] = by_tool.get(issue.tool, 0) + 1

        return {"total": len(issues), "by_severity": by_severity, "by_tool": by_tool}


if __name__ == "__main__":
    # Example usage
    analyzer = StaticAnalyzer()

    # Example Python code with issues
    sample_code = """
def example_function():
    password = "hardcoded123"  # Security issue
    eval("print('hello')")      # Security issue
    unused_variable = 42        # Flake8 issue
    return password
"""

    issues = analyzer.analyze_diff_content(sample_code, "example.py", ".py")

    print("Analysis Results:")
    for issue in issues:
        print(
            f"  {issue.tool}: {issue.severity} - {issue.message} (line {issue.line_number})"
        )

    summary = analyzer.get_issue_summary(issues)
    print(f"\nSummary: {summary}")
