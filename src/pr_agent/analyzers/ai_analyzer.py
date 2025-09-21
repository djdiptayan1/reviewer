"""
AI-powered code analyzer using Google Gemini for intelligent code review.

This module provides functionality to analyze code changes using AI
and generate intelligent feedback on code quality, structure, and potential issues.
"""

import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import google.generativeai as genai


@dataclass
class AIFeedback:
    """Represents detailed AI-generated feedback for code review."""

    file_path: Optional[str]
    line_number: Optional[int]
    position: Optional[int]  # Position in diff for inline comments
    severity: str  # critical, error, warning, suggestion, info
    category: str  # security, performance, architecture, maintainability, style, testing, documentation
    title: str  # Brief descriptive title
    message: str  # Detailed explanation with context and impact
    suggestion: Optional[str] = None  # Specific code solution with examples
    reasoning: Optional[str] = None  # Why this matters and consequences
    alternatives: Optional[str] = None  # Other possible approaches
    confidence: float = 0.8  # AI confidence in the feedback (0-1)
    priority: str = "medium"  # high, medium, low


@dataclass
class CodeQualityScore:
    """Represents detailed code quality scoring."""

    overall: int  # 0-100
    security: int  # 0-100
    performance: int  # 0-100
    maintainability: int  # 0-100
    architecture: int  # 0-100
    testing: int  # 0-100
    documentation: int  # 0-100


class AIAnalyzer:
    """AI-powered code analyzer using Google Gemini."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        """
        Initialize the AI analyzer.

        Args:
            api_key: Google Gemini API key
            model: Gemini model to use for analysis
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable."
            )

        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = model

        # Initialize the model
        self.client = genai.GenerativeModel(model_name=model)

        # System prompt for code review
        self.system_prompt = """You are a senior software architect and security expert with 15+ years of experience reviewing code across multiple languages and domains. You have deep expertise in:

- Software architecture and design patterns
- Security vulnerabilities and attack vectors  
- Performance optimization and scalability
- Code maintainability and technical debt
- Testing strategies and coverage
- Modern development practices and standards

ANALYSIS REQUIREMENTS:
Your review must be thorough, detailed, and actionable. For each issue you identify:

1. CONTEXT: Explain why this is an issue in the broader codebase context
2. IMPACT: Describe potential consequences (performance, security, maintainability)
3. SOLUTION: Provide specific, implementable solutions with code examples
4. PRIORITY: Assess urgency and importance
5. ALTERNATIVES: When applicable, mention multiple approaches

DETAILED ANALYSIS AREAS:
1. **Architecture & Design**:
   - Evaluate design patterns usage and appropriateness
   - Check for SOLID principles violations
   - Assess module coupling and cohesion
   - Review abstraction levels and interfaces

2. **Security Analysis**:
   - Input validation and sanitization
   - Authentication and authorization flows
   - Data exposure and privacy concerns
   - Injection vulnerabilities (SQL, XSS, etc.)
   - Cryptographic practices

3. **Performance & Scalability**:
   - Algorithm complexity analysis
   - Database query optimization
   - Memory usage patterns
   - Caching strategies
   - Async/concurrency patterns

4. **Code Quality & Maintainability**:
   - Code readability and documentation
   - Error handling patterns
   - Testing coverage and quality
   - Code duplication and refactoring opportunities
   - Naming conventions and clarity

5. **Technical Debt Assessment**:
   - Identify future maintenance burdens
   - Suggest refactoring priorities
   - Point out deprecated patterns or libraries

RESPONSE FORMAT:
Return detailed analysis as JSON with "feedback" array and "score" object:

{
  "feedback": [
    {
      "file_path": "string|null",
      "line_number": "number|null", 
      "position": "number|null",
      "severity": "critical|error|warning|suggestion|info",
      "category": "security|performance|architecture|maintainability|style|testing|documentation",
      "title": "Brief descriptive title",
      "message": "Detailed explanation with context and impact",
      "suggestion": "Specific code solution with examples",
      "reasoning": "Why this matters and potential consequences",
      "alternatives": "Other possible approaches (if applicable)",
      "confidence": 0.0-1.0,
      "priority": "high|medium|low"
    }
  ],
  "score": {
    "overall": 0-100,
    "security": 0-100,
    "performance": 0-100, 
    "maintainability": 0-100,
    "architecture": 0-100,
    "testing": 0-100,
    "documentation": 0-100
  },
  "summary": "Overall assessment with key recommendations"
}

GUIDELINES:
- Provide specific, actionable feedback with code examples
- Explain the "why" behind each recommendation
- Consider the broader system impact
- Balance perfectionism with pragmatism
- Prioritize security and critical issues
- Limit to 15 most important feedback items
- Give constructive, professional tone"""

    def analyze_diff(
        self, diff_text: str, pr_info: Optional[Dict[str, Any]] = None
    ) -> tuple[List[AIFeedback], Optional[CodeQualityScore], Optional[str]]:
        """
        Analyze a diff using AI and return detailed feedback with scoring.

        Args:
            diff_text: Unified diff text to analyze
            pr_info: Optional PR metadata (title, description, etc.)

        Returns:
            Tuple of (feedback_list, quality_score, summary)
        """
        if not diff_text.strip():
            return [], None, None

        try:
            # Prepare context
            context = self._prepare_context(diff_text, pr_info)

            # Create the full prompt
            full_prompt = f"{self.system_prompt}\n\n{context}"

            # Call Gemini API with enhanced parameters
            response = self.client.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Low temperature for consistent, focused reviews
                    max_output_tokens=4000,  # Increased for detailed feedback
                ),
            )

            # Parse response
            content = response.text.strip()

            # Extract JSON from response if it's wrapped in markdown
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()

            feedback_data = json.loads(content)

            # Parse feedback items
            feedback_list = []
            if isinstance(feedback_data, dict) and "feedback" in feedback_data:
                feedback_items = feedback_data["feedback"]
            elif isinstance(feedback_data, list):
                feedback_items = feedback_data
                feedback_data = {"feedback": feedback_items}  # Ensure dict format
            else:
                return [], None, None

            for item in feedback_items:
                if isinstance(item, dict):
                    feedback = AIFeedback(
                        file_path=item.get("file_path"),
                        line_number=item.get("line_number"),
                        position=item.get("position"),
                        severity=item.get("severity", "info"),
                        category=item.get("category", "general"),
                        title=item.get("title", "Code Review Item"),
                        message=item.get("message", ""),
                        suggestion=item.get("suggestion"),
                        reasoning=item.get("reasoning"),
                        alternatives=item.get("alternatives"),
                        confidence=float(item.get("confidence", 0.8)),
                        priority=item.get("priority", "medium"),
                    )
                    feedback_list.append(feedback)

            # Parse quality score
            quality_score = None
            if "score" in feedback_data and isinstance(feedback_data["score"], dict):
                score_data = feedback_data["score"]
                quality_score = CodeQualityScore(
                    overall=score_data.get("overall", 75),
                    security=score_data.get("security", 75),
                    performance=score_data.get("performance", 75),
                    maintainability=score_data.get("maintainability", 75),
                    architecture=score_data.get("architecture", 75),
                    testing=score_data.get("testing", 75),
                    documentation=score_data.get("documentation", 75),
                )

            # Get summary
            summary = feedback_data.get("summary", "")

            return feedback_list, quality_score, summary

        except json.JSONDecodeError as e:
            print(f"Failed to parse AI response as JSON: {e}")
            print(f"Response content: {content}")
            return [], None, None

        except Exception as e:
            print(f"AI analysis failed: {e}")
            return [], None, None

    def analyze_files(
        self, files_content: Dict[str, str], changed_lines: Dict[str, List[int]]
    ) -> List[AIFeedback]:
        """
        Analyze specific files with their content and changed lines.

        Args:
            files_content: Mapping of file_path to file content
            changed_lines: Mapping of file_path to list of changed line numbers

        Returns:
            List of AI-generated feedback
        """
        feedback_list = []

        for file_path, content in files_content.items():
            if not content.strip():
                continue

            try:
                # Prepare file-specific context
                context = self._prepare_file_context(
                    file_path, content, changed_lines.get(file_path, [])
                )

                # Create the full prompt
                full_prompt = f"{self.system_prompt}\n\n{context}"

                # Call Gemini API
                response = self.client.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=1500,
                    ),
                )

                # Parse and add to feedback list
                content_response = response.text.strip()

                # Extract JSON from response if it's wrapped in markdown
                if "```json" in content_response:
                    start = content_response.find("```json") + 7
                    end = content_response.find("```", start)
                    content_response = content_response[start:end].strip()
                elif "```" in content_response:
                    start = content_response.find("```") + 3
                    end = content_response.find("```", start)
                    content_response = content_response[start:end].strip()

                feedback_data = json.loads(content_response)

                if isinstance(feedback_data, dict) and "feedback" in feedback_data:
                    feedback_items = feedback_data["feedback"]
                elif isinstance(feedback_data, list):
                    feedback_items = feedback_data
                else:
                    continue

                for item in feedback_items:
                    if isinstance(item, dict):
                        feedback = AIFeedback(
                            file_path=file_path,
                            line_number=item.get("line_number"),
                            position=item.get("position"),
                            severity=item.get("severity", "info"),
                            category=item.get("category", "general"),
                            message=item.get("message", ""),
                            suggestion=item.get("suggestion"),
                            confidence=float(item.get("confidence", 0.8)),
                        )
                        feedback_list.append(feedback)

            except Exception as e:
                # Add error feedback for this file
                feedback_list.append(
                    AIFeedback(
                        file_path=file_path,
                        line_number=None,
                        position=None,
                        severity="warning",
                        category="general",
                        message=f"AI analysis failed for this file: {str(e)}",
                        confidence=0.1,
                    )
                )

        return feedback_list

    def generate_summary(
        self, all_feedback: List[AIFeedback], pr_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a summary of all feedback for the PR.

        Args:
            all_feedback: List of all feedback items
            pr_info: Optional PR metadata

        Returns:
            Summary text for the PR comment
        """
        if not all_feedback:
            return "🤖 **AI Code Review Summary**\n\nNo significant issues found. Code looks good! ✅"

        # Count issues by severity and category
        severity_counts = {}
        category_counts = {}
        high_confidence_issues = []

        for feedback in all_feedback:
            severity_counts[feedback.severity] = (
                severity_counts.get(feedback.severity, 0) + 1
            )
            category_counts[feedback.category] = (
                category_counts.get(feedback.category, 0) + 1
            )

            if feedback.confidence >= 0.8 and feedback.severity in ["error", "warning"]:
                high_confidence_issues.append(feedback)

        # Build summary
        summary = ["🤖 **AI Code Review Summary**\n"]

        # Overall stats
        total_issues = len(all_feedback)
        summary.append(f"**Total Issues Found:** {total_issues}")

        if severity_counts:
            severity_parts = []
            for severity in ["error", "warning", "suggestion", "info"]:
                count = severity_counts.get(severity, 0)
                if count > 0:
                    emoji = {
                        "error": "🚨",
                        "warning": "⚠️",
                        "suggestion": "💡",
                        "info": "ℹ️",
                    }
                    severity_parts.append(f"{emoji[severity]} {count} {severity}")

            if severity_parts:
                summary.append(f"**Breakdown:** {' | '.join(severity_parts)}")

        # Top categories
        if category_counts:
            top_categories = sorted(
                category_counts.items(), key=lambda x: x[1], reverse=True
            )[:3]
            category_parts = [f"{cat} ({count})" for cat, count in top_categories]
            summary.append(f"**Main Areas:** {', '.join(category_parts)}")

        # High confidence issues
        if high_confidence_issues:
            summary.append("\n**🔍 Key Issues to Address:**")
            for feedback in high_confidence_issues[:5]:  # Limit to top 5
                file_info = f" in `{feedback.file_path}`" if feedback.file_path else ""
                line_info = (
                    f" (line {feedback.line_number})" if feedback.line_number else ""
                )
                summary.append(f"- {feedback.message}{file_info}{line_info}")

        summary.append(
            f"\n**📊 Review Confidence:** {self._calculate_overall_confidence(all_feedback):.0%}"
        )
        summary.append(
            "\n*This review was generated by AI. Please use your judgment for final decisions.*"
        )

        return "\n".join(summary)

    def _prepare_context(
        self, diff_text: str, pr_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Prepare context for AI analysis."""
        context_parts = []

        if pr_info:
            context_parts.append(f"**PR Title:** {pr_info.get('title', 'N/A')}")
            if pr_info.get("description"):
                context_parts.append(
                    f"**PR Description:** {pr_info['description'][:500]}..."
                )

        context_parts.append("**Code Changes:**")
        context_parts.append("```diff")

        # Truncate diff if too long
        if len(diff_text) > 8000:
            diff_text = diff_text[:8000] + "\n\n... (diff truncated for analysis)"

        context_parts.append(diff_text)
        context_parts.append("```")

        context_parts.append(
            "\nPlease analyze these changes and provide feedback as a JSON response with 'feedback' array."
        )

        return "\n".join(context_parts)

    def _prepare_file_context(
        self, file_path: str, content: str, changed_lines: List[int]
    ) -> str:
        """Prepare context for analyzing a specific file."""
        context_parts = []

        context_parts.append(f"**File:** {file_path}")

        if changed_lines:
            context_parts.append(
                f"**Changed Lines:** {', '.join(map(str, changed_lines[:10]))}"
            )

        context_parts.append("**File Content:**")
        context_parts.append(f"```{self._get_language_from_path(file_path)}")

        # Truncate content if too long
        if len(content) > 6000:
            lines = content.split("\n")
            if changed_lines:
                # Focus on changed lines with context
                relevant_lines = set()
                for line_num in changed_lines:
                    for i in range(
                        max(1, line_num - 5), min(len(lines) + 1, line_num + 6)
                    ):
                        relevant_lines.add(i)

                if relevant_lines:
                    truncated_lines = []
                    sorted_lines = sorted(relevant_lines)
                    for i, line_num in enumerate(sorted_lines):
                        if i > 0 and line_num > sorted_lines[i - 1] + 1:
                            truncated_lines.append("... (lines omitted) ...")
                        truncated_lines.append(
                            f"{line_num}: {lines[line_num-1] if line_num <= len(lines) else ''}"
                        )
                    content = "\n".join(truncated_lines)
            else:
                content = content[:6000] + "\n\n... (content truncated)"

        context_parts.append(content)
        context_parts.append("```")

        context_parts.append(
            "\nPlease analyze this file and provide feedback as a JSON response with 'feedback' array."
        )

        return "\n".join(context_parts)

    def _get_language_from_path(self, file_path: str) -> str:
        """Get language identifier from file path for syntax highlighting."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".tsx": "tsx",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".go": "go",
            ".rs": "rust",
            ".php": "php",
            ".rb": "ruby",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".sh": "bash",
            ".sql": "sql",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".xml": "xml",
            ".md": "markdown",
        }

        for ext, lang in extension_map.items():
            if file_path.lower().endswith(ext):
                return lang

        return "text"

    def _calculate_overall_confidence(self, feedback_list: List[AIFeedback]) -> float:
        """Calculate overall confidence score for the review."""
        if not feedback_list:
            return 1.0

        total_confidence = sum(feedback.confidence for feedback in feedback_list)
        return total_confidence / len(feedback_list)


if __name__ == "__main__":
    # Example usage
    import os

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    try:
        analyzer = AIAnalyzer()

        # Example diff
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

        feedback = analyzer.analyze_diff(sample_diff)

        print("AI Analysis Results:")
        for item in feedback:
            print(f"  {item.severity}: {item.message}")
            if item.suggestion:
                print(f"    Suggestion: {item.suggestion}")

        summary = analyzer.generate_summary(feedback)
        print(f"\nSummary:\n{summary}")

    except ValueError as e:
        print(f"Error: {e}")
        print("Make sure to set GEMINI_API_KEY environment variable")
