"""
Reporter module for formatting and posting PR review feedback.

This module handles the formatting of analysis results and posting them
as comments on pull requests through the appropriate git server adapter.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .adapters.base_adapter import BaseAdapter, ReviewComment
from .analyzers.static_analyzer import AnalysisIssue
from .analyzers.ai_analyzer import AIFeedback


@dataclass
class ReviewSummary:
    """Summary of a complete PR review."""

    total_issues: int
    static_issues: int
    ai_feedback: int
    severity_breakdown: Dict[str, int]
    files_analyzed: int
    review_time: str
    confidence_score: float


class Reporter:
    """Handles formatting and posting of PR review results."""

    def __init__(self, adapter: BaseAdapter):
        """
        Initialize the reporter.

        Args:
            adapter: Git server adapter for posting comments
        """
        self.adapter = adapter

    def post_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        static_issues: List[AnalysisIssue],
        ai_feedback: List[AIFeedback],
        pr_info: Optional[Dict[str, Any]] = None,
        post_inline: bool = True,
        post_summary: bool = True,
        quality_score: Optional[Any] = None,
        ai_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Post complete review with summary and inline comments.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            static_issues: List of static analysis issues
            ai_feedback: List of AI-generated feedback
            pr_info: Optional PR metadata
            post_inline: Whether to post inline comments
            post_summary: Whether to post summary comment
            quality_score: Optional code quality scoring
            ai_summary: Optional AI-generated summary

        Returns:
            Dictionary with posting results
        """
        results = {"summary_posted": False, "inline_comments": 0, "errors": []}

        try:
            # Generate summary
            summary = self.generate_summary(
                static_issues, ai_feedback, pr_info, quality_score, ai_summary
            )
            review_summary = self._create_review_summary(static_issues, ai_feedback)

            # Post summary comment
            if post_summary:
                try:
                    self.adapter.post_review_comment(owner, repo, pr_number, summary)
                    results["summary_posted"] = True
                except Exception as e:
                    results["errors"].append(f"Failed to post summary: {str(e)}")

            # Post inline comments
            if post_inline:
                inline_count = 0

                # Post static analysis inline comments
                for issue in static_issues:
                    if issue.line_number and issue.file_path:
                        try:
                            comment = ReviewComment(
                                body=self._format_static_issue_comment(issue),
                                file_path=issue.file_path,
                                line_number=issue.line_number,
                                severity=issue.severity,
                            )
                            self.adapter.post_inline_comment(
                                owner, repo, pr_number, comment
                            )
                            inline_count += 1
                        except Exception as e:
                            results["errors"].append(
                                f"Failed to post inline comment for {issue.file_path}:{issue.line_number}: {str(e)}"
                            )

                # Post AI feedback inline comments
                for feedback in ai_feedback:
                    if (
                        feedback.line_number
                        and feedback.file_path
                        and feedback.severity in ["warning", "error"]
                    ):
                        try:
                            comment = ReviewComment(
                                body=self._format_ai_feedback_comment(feedback),
                                file_path=feedback.file_path,
                                line_number=feedback.line_number,
                                position=feedback.position,
                                severity=feedback.severity,
                            )
                            self.adapter.post_inline_comment(
                                owner, repo, pr_number, comment
                            )
                            inline_count += 1
                        except Exception as e:
                            results["errors"].append(
                                f"Failed to post AI feedback for {feedback.file_path}:{feedback.line_number}: {str(e)}"
                            )

                results["inline_comments"] = inline_count

            return results

        except Exception as e:
            results["errors"].append(f"Review posting failed: {str(e)}")
            return results

    def generate_summary(
        self,
        static_issues: List[AnalysisIssue],
        ai_feedback: List[AIFeedback],
        pr_info: Optional[Dict[str, Any]] = None,
        quality_score: Optional[Any] = None,
        ai_summary: Optional[str] = None,
    ) -> str:
        """
        Generate a comprehensive summary comment with quality scoring.

        Args:
            static_issues: List of static analysis issues
            ai_feedback: List of AI feedback
            pr_info: Optional PR information
            quality_score: Optional code quality scoring
            ai_summary: Optional AI-generated summary

        Returns:
            Formatted summary text
        """
        lines = []

        # Header
        lines.append("# PR Review Agent Report")
        lines.append("")

        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append(f"**Review completed at:** {timestamp}")
        lines.append("")

        # Add quality scoring if available
        if quality_score:
            lines.append("## Code Quality Score")
            lines.append("")
            lines.append(f"**Overall Score: {quality_score.overall}/100**")
            lines.append("")
            lines.append("### Detailed Breakdown:")
            lines.append(f"- **Security:** {quality_score.security}/100")
            lines.append(f"- **Performance:** {quality_score.performance}/100")
            lines.append(f"- **Maintainability:** {quality_score.maintainability}/100")
            lines.append(f"- **Architecture:** {quality_score.architecture}/100")
            lines.append(f"- **Testing:** {quality_score.testing}/100")
            lines.append(f"- **Documentation:** {quality_score.documentation}/100")
            lines.append("")

        # Add AI summary if available
        if ai_summary:
            lines.append("## Executive Summary")
            lines.append("")
            lines.append(ai_summary)
            lines.append("")

        # Overview statistics
        total_static = len(static_issues)
        total_ai = len(ai_feedback)
        total_issues = total_static + total_ai

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total Issues Found:** {total_issues}")
        lines.append(f"- **Static Analysis Issues:** {total_static}")
        lines.append(f"- **AI Feedback Items:** {total_ai}")

        # Severity breakdown
        severity_counts = self._count_by_severity(static_issues, ai_feedback)
        if severity_counts:
            lines.append("")
            lines.append("### Issue Severity Breakdown")
            for severity, count in severity_counts.items():
                lines.append(f"- **{severity.title()}:** {count}")

        # Category breakdown for AI feedback
        ai_categories = self._count_ai_categories(ai_feedback)
        if ai_categories:
            lines.append("")
            lines.append("### AI Feedback Categories")
            for category, count in sorted(
                ai_categories.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"- **{category.title()}:** {count}")

        # Static analysis tools summary
        static_tools = self._count_static_tools(static_issues)
        if static_tools:
            lines.append("")
            lines.append("### Static Analysis Tools")
            for tool, count in static_tools.items():
                lines.append(f"- **{tool}:** {count} issues")

        # High priority issues
        high_priority = self._get_high_priority_issues(static_issues, ai_feedback)
        if high_priority:
            lines.append("")
            lines.append("## High Priority Issues")
            lines.append("")
            for issue in high_priority[:5]:  # Limit to top 5
                if isinstance(issue, AnalysisIssue):
                    lines.append(
                        f"- **{issue.file_path}** (line {issue.line_number}): {issue.message}"
                    )
                elif isinstance(issue, AIFeedback):
                    file_info = (
                        f"**{issue.file_path}**" if issue.file_path else "General"
                    )
                    line_info = (
                        f" (line {issue.line_number})" if issue.line_number else ""
                    )
                    lines.append(f"- {file_info}{line_info}: {issue.message}")

        # Recommendations
        recommendations = self._generate_recommendations(static_issues, ai_feedback)
        if recommendations:
            lines.append("")
            lines.append("## Recommendations")
            lines.append("")
            for rec in recommendations:
                lines.append(f"- {rec}")

        # AI confidence note
        ai_confidence = self._calculate_ai_confidence(ai_feedback)
        if ai_feedback and ai_confidence:
            lines.append("")
            lines.append(f"**AI Review Confidence:** {ai_confidence:.0%}")

        # Footer
        lines.append("")
        lines.append("---")
        lines.append(
            "*This review was generated automatically. Please use your judgment for final decisions.*"
        )
        lines.append("")
        lines.append("**Tools used:** Static analysis + AI-powered review")

        return "\n".join(lines)

    def _format_static_issue_comment(self, issue: AnalysisIssue) -> str:
        """Format a static analysis issue as an enhanced inline comment."""
        lines = [
            f"**{issue.tool.upper()}** - {issue.severity.title()} ({issue.category.title()})"
        ]
        lines.append("")

        if hasattr(issue, "rule_id") and issue.rule_id:
            lines.append(f"**Rule:** `{issue.rule_id}`")

        lines.append(f"**Issue:** {issue.message}")

        if hasattr(issue, "description") and issue.description:
            lines.append("")
            lines.append("**Details:**")
            lines.append(issue.description)

        if hasattr(issue, "suggestion") and issue.suggestion:
            lines.append("")
            lines.append("**How to fix:**")
            lines.append(issue.suggestion)

        if hasattr(issue, "documentation_url") and issue.documentation_url:
            lines.append("")
            lines.append(
                f"**Documentation:** [View Rule Details]({issue.documentation_url})"
            )

        return "\n".join(lines)

    def _format_ai_feedback_comment(self, feedback: AIFeedback) -> str:
        """Format enhanced AI feedback as an inline comment."""
        lines = [
            f"**AI Review** - {feedback.category.title()} ({feedback.severity.title()})"
        ]
        lines.append("")
        lines.append(f"**{feedback.title}**")
        lines.append("")
        lines.append(feedback.message)

        if feedback.reasoning:
            lines.append("")
            lines.append("**Why this matters:**")
            lines.append(feedback.reasoning)

        if feedback.suggestion:
            lines.append("")
            lines.append("**Suggested improvement:**")
            lines.append("```")
            lines.append(feedback.suggestion)
            lines.append("```")

        if feedback.alternatives:
            lines.append("")
            lines.append("**Alternative approaches:**")
            lines.append(feedback.alternatives)

        confidence_bar = "▓" * int(feedback.confidence * 5) + "░" * (
            5 - int(feedback.confidence * 5)
        )
        lines.append(
            f"\n*Priority: {feedback.priority.title()} | Confidence: {confidence_bar} {feedback.confidence:.0%}*"
        )

        return "\n".join(lines)

    def _create_review_summary(
        self, static_issues: List[AnalysisIssue], ai_feedback: List[AIFeedback]
    ) -> ReviewSummary:
        """Create a structured review summary."""
        severity_breakdown = self._count_by_severity(static_issues, ai_feedback)
        files_analyzed = len(
            set(
                [issue.file_path for issue in static_issues if issue.file_path]
                + [feedback.file_path for feedback in ai_feedback if feedback.file_path]
            )
        )

        confidence_score = self._calculate_ai_confidence(ai_feedback)

        return ReviewSummary(
            total_issues=len(static_issues) + len(ai_feedback),
            static_issues=len(static_issues),
            ai_feedback=len(ai_feedback),
            severity_breakdown=severity_breakdown,
            files_analyzed=files_analyzed,
            review_time=datetime.now().isoformat(),
            confidence_score=confidence_score,
        )

    def _count_by_severity(
        self, static_issues: List[AnalysisIssue], ai_feedback: List[AIFeedback]
    ) -> Dict[str, int]:
        """Count issues by severity level."""
        counts = {}

        for issue in static_issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1

        for feedback in ai_feedback:
            counts[feedback.severity] = counts.get(feedback.severity, 0) + 1

        return counts

    def _count_ai_categories(self, ai_feedback: List[AIFeedback]) -> Dict[str, int]:
        """Count AI feedback by category."""
        counts = {}
        for feedback in ai_feedback:
            counts[feedback.category] = counts.get(feedback.category, 0) + 1
        return counts

    def _count_static_tools(self, static_issues: List[AnalysisIssue]) -> Dict[str, int]:
        """Count static issues by tool."""
        counts = {}
        for issue in static_issues:
            counts[issue.tool] = counts.get(issue.tool, 0) + 1
        return counts

    def _get_high_priority_issues(
        self, static_issues: List[AnalysisIssue], ai_feedback: List[AIFeedback]
    ) -> List[Any]:
        """Get high priority issues for summary."""
        high_priority = []

        # High priority static issues
        for issue in static_issues:
            if issue.severity in ["error"]:
                high_priority.append(issue)

        # High confidence AI feedback
        for feedback in ai_feedback:
            if feedback.severity in ["error", "warning"] and feedback.confidence >= 0.8:
                high_priority.append(feedback)

        return high_priority

    def _generate_recommendations(
        self, static_issues: List[AnalysisIssue], ai_feedback: List[AIFeedback]
    ) -> List[str]:
        """Generate general recommendations based on analysis."""
        recommendations = []

        # Check for common patterns
        severity_counts = self._count_by_severity(static_issues, ai_feedback)

        if severity_counts.get("error", 0) > 0:
            recommendations.append("Fix critical errors before merging")

        if severity_counts.get("warning", 0) > 5:
            recommendations.append(
                "Consider addressing warnings to improve code quality"
            )

        # AI category-based recommendations
        ai_categories = self._count_ai_categories(ai_feedback)

        if ai_categories.get("security", 0) > 0:
            recommendations.append("Review security-related feedback carefully")

        if ai_categories.get("performance", 0) > 2:
            recommendations.append("Consider performance optimizations suggested by AI")

        if ai_categories.get("maintainability", 0) > 3:
            recommendations.append(
                "Address maintainability concerns for better long-term code health"
            )

        return recommendations

    def _calculate_ai_confidence(self, ai_feedback: List[AIFeedback]) -> float:
        """Calculate average AI confidence score."""
        if not ai_feedback:
            return 0.0

        total_confidence = sum(feedback.confidence for feedback in ai_feedback)
        return total_confidence / len(ai_feedback)

    def _get_severity_emoji(self, severity: str) -> str:
        """Get emoji for severity level - DEPRECATED: Remove emoji usage."""
        return ""  # No more emojis

    def _get_category_emoji(self, category: str) -> str:
        """Get emoji for feedback category - DEPRECATED: Remove emoji usage."""
        return ""  # No more emojis


if __name__ == "__main__":
    # Example usage - this would normally use a real adapter
    from .adapters.base_adapter import BaseAdapter
    from .analyzers.static_analyzer import AnalysisIssue
    from .analyzers.ai_analyzer import AIFeedback

    # Mock adapter for testing
    class MockAdapter(BaseAdapter):
        def __init__(self):
            pass

        def get_pr_info(self, owner, repo, pr_number):
            return None

        def get_pr_files(self, owner, repo, pr_number):
            return []

        def get_pr_diff(self, owner, repo, pr_number):
            return ""

        def post_review_comment(self, owner, repo, pr_number, body):
            print(f"Posted summary comment:\n{body}")
            return {"id": 123}

        def post_inline_comment(self, owner, repo, pr_number, comment):
            print(f"Posted inline comment on {comment.file_path}:{comment.line_number}")
            print(f"Body: {comment.body}")
            return {"id": 124}

        def validate_credentials(self):
            return True

    # Create sample issues
    static_issues = [
        AnalysisIssue(
            tool="flake8",
            file_path="example.py",
            line_number=10,
            column=5,
            severity="warning",
            code="E501",
            message="Line too long (90 > 79 characters)",
        )
    ]

    ai_feedback = [
        AIFeedback(
            file_path="example.py",
            line_number=15,
            position=None,
            severity="suggestion",
            category="maintainability",
            message="Consider extracting this complex logic into a separate function",
            confidence=0.85,
        )
    ]

    # Test reporter
    adapter = MockAdapter()
    reporter = Reporter(adapter)

    summary = reporter.generate_summary(static_issues, ai_feedback)
    print("Generated Summary:")
    print(summary)
