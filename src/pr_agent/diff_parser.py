"""
Diff parser for analyzing unified diffs and extracting line information.

This module provides functionality to parse unified diff text and extract
information about changed lines, file modifications, and position mapping
for inline comments.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from unidiff import PatchSet, PatchedFile
import re


@dataclass
class LineChange:
    """Represents a single line change in a diff."""

    file_path: str
    line_number: int
    position: int
    line_content: str
    change_type: str  # added, removed, context
    target_line_no: Optional[int] = None
    source_line_no: Optional[int] = None


@dataclass
class FileAnalysis:
    """Analysis results for a single file."""

    file_path: str
    additions: int
    deletions: int
    is_new_file: bool
    is_deleted_file: bool
    is_renamed: bool
    old_path: Optional[str] = None
    line_changes: List[LineChange] = None

    def __post_init__(self):
        if self.line_changes is None:
            self.line_changes = []


class DiffParser:
    """Parser for unified diff text."""

    def __init__(self, diff_text: str):
        """
        Initialize the diff parser.

        Args:
            diff_text: Unified diff text to parse
        """
        self.diff_text = diff_text
        self.patch_set = PatchSet(diff_text) if diff_text.strip() else None

    def get_files(self) -> List[str]:
        """Get list of all files modified in the diff."""
        if not self.patch_set:
            return []

        return [patched_file.path for patched_file in self.patch_set]

    def get_file_analysis(self, file_path: str) -> Optional[FileAnalysis]:
        """
        Get detailed analysis for a specific file.

        Args:
            file_path: Path of the file to analyze

        Returns:
            FileAnalysis object or None if file not found
        """
        if not self.patch_set:
            return None

        patched_file = self._find_file(file_path)
        if not patched_file:
            return None

        return self._analyze_file(patched_file)

    def get_all_file_analyses(self) -> List[FileAnalysis]:
        """Get analysis for all files in the diff."""
        if not self.patch_set:
            return []

        analyses = []
        for patched_file in self.patch_set:
            analysis = self._analyze_file(patched_file)
            analyses.append(analysis)

        return analyses

    def get_added_lines_with_positions(self) -> Dict[str, List[Tuple[int, int, str]]]:
        """
        Get mapping of added lines with their positions for inline comments.

        Returns:
            Dictionary mapping file_path to list of (position, line_number, content) tuples
        """
        if not self.patch_set:
            return {}

        result = {}

        for patched_file in self.patch_set:
            file_path = patched_file.path
            added_lines = []
            position = 0

            for hunk in patched_file:
                for line in hunk:
                    position += 1
                    if line.is_added:
                        added_lines.append(
                            (position, line.target_line_no, line.value.rstrip("\n"))
                        )

            if added_lines:
                result[file_path] = added_lines

        return result

    def get_modified_lines_context(
        self, file_path: str, line_number: int, context_lines: int = 3
    ) -> Optional[str]:
        """
        Get context around a modified line.

        Args:
            file_path: Path of the file
            line_number: Line number to get context for
            context_lines: Number of context lines before and after

        Returns:
            Context string or None if not found
        """
        patched_file = self._find_file(file_path)
        if not patched_file:
            return None

        target_lines = []
        for hunk in patched_file:
            for line in hunk:
                if (
                    line.target_line_no
                    and abs(line.target_line_no - line_number) <= context_lines
                ):
                    prefix = "+" if line.is_added else "-" if line.is_removed else " "
                    target_lines.append(f"{prefix} {line.value.rstrip()}")

        return "\n".join(target_lines) if target_lines else None

    def get_statistics(self) -> Dict[str, int]:
        """Get overall statistics for the diff."""
        if not self.patch_set:
            return {"files": 0, "additions": 0, "deletions": 0}

        files = len(self.patch_set)
        additions = sum(patched_file.added for patched_file in self.patch_set)
        deletions = sum(patched_file.removed for patched_file in self.patch_set)

        return {"files": files, "additions": additions, "deletions": deletions}

    def is_large_diff(self, threshold: int = 1000) -> bool:
        """Check if the diff is considered large based on total changes."""
        stats = self.get_statistics()
        return (stats["additions"] + stats["deletions"]) > threshold

    def extract_function_changes(self, file_path: str) -> List[Dict[str, str]]:
        """
        Extract function-level changes from a file.

        This is a basic implementation that looks for function definitions.
        A more sophisticated version would use language-specific parsers.

        Args:
            file_path: Path of the file to analyze

        Returns:
            List of function changes with metadata
        """
        patched_file = self._find_file(file_path)
        if not patched_file:
            return []

        function_changes = []

        # Basic patterns for common languages
        function_patterns = {
            ".py": [r"^\s*def\s+(\w+)", r"^\s*class\s+(\w+)"],
            ".js": [r"^\s*function\s+(\w+)", r"^\s*const\s+(\w+)\s*="],
            ".java": [r"^\s*(?:public|private|protected)?\s*\w+\s+(\w+)\s*\("],
            ".go": [r"^\s*func\s+(\w+)"],
        }

        # Determine file type
        file_ext = None
        for ext in function_patterns:
            if file_path.endswith(ext):
                file_ext = ext
                break

        if not file_ext:
            return function_changes

        for hunk in patched_file:
            for line in hunk:
                if line.is_added or line.is_removed:
                    for pattern in function_patterns[file_ext]:
                        match = re.match(pattern, line.value)
                        if match:
                            function_changes.append(
                                {
                                    "function_name": match.group(1),
                                    "change_type": (
                                        "added" if line.is_added else "removed"
                                    ),
                                    "line_number": line.target_line_no
                                    or line.source_line_no,
                                    "content": line.value.strip(),
                                }
                            )

        return function_changes

    def _find_file(self, file_path: str) -> Optional[PatchedFile]:
        """Find a patched file by path."""
        if not self.patch_set:
            return None

        for patched_file in self.patch_set:
            if patched_file.path == file_path:
                return patched_file
        return None

    def _analyze_file(self, patched_file: PatchedFile) -> FileAnalysis:
        """Analyze a single patched file."""
        line_changes = []
        position = 0

        for hunk in patched_file:
            for line in hunk:
                position += 1
                change_type = "context"
                if line.is_added:
                    change_type = "added"
                elif line.is_removed:
                    change_type = "removed"

                line_change = LineChange(
                    file_path=patched_file.path,
                    line_number=line.target_line_no or line.source_line_no or 0,
                    position=position,
                    line_content=line.value.rstrip("\n"),
                    change_type=change_type,
                    target_line_no=line.target_line_no,
                    source_line_no=line.source_line_no,
                )
                line_changes.append(line_change)

        return FileAnalysis(
            file_path=patched_file.path,
            additions=patched_file.added,
            deletions=patched_file.removed,
            is_new_file=patched_file.is_added_file,
            is_deleted_file=patched_file.is_removed_file,
            is_renamed=patched_file.is_rename,
            old_path=patched_file.source_file if patched_file.is_rename else None,
            line_changes=line_changes,
        )


if __name__ == "__main__":
    # Example usage
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
    print("Files modified:", parser.get_files())
    print("Statistics:", parser.get_statistics())

    # Get added lines with positions
    added_lines = parser.get_added_lines_with_positions()
    for file_path, lines in added_lines.items():
        print(f"\nAdded lines in {file_path}:")
        for position, line_num, content in lines:
            print(f"  Position {position}, Line {line_num}: {content}")
