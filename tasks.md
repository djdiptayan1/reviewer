# PR Review Agent — Quick-start & Implementation Guide

**Goal:** build a modular Python agent that can review Pull Requests (PRs) across multiple git servers (GitHub, GitLab, Bitbucket), analyze diffs, run automated checks (linters, security scanners, type-checkers), call an LLM for AI-driven feedback, and post inline comments and a summary report.

This document is written to be dropped into VS Code as `PR-Review-Agent-Instructions.md`. It contains a prioritized MVP plan, architecture, full directory layout, code snippets you can copy/paste, CI examples, and *ready-to-use AI agent prompts* so you can have an LLM implement modules for you.

---

## 1 — MVP & Priorities (what to implement first)

**MVP features (minimum to ship quickly)**

* Generic adapter interface for Git providers (fetch PR metadata & files, post comments). Implement at least GitHub and provide stubs for GitLab/Bitbucket.
* Fetch PR diffs and parse them into file hunks.
* Run quickly-available static checks: `flake8` (Python), `eslint` (JS) or run language-agnostic heuristics.
* Simple AI-based analyzer that receives diff+context and outputs suggestions (using Gemini or another LLM backend).
* Post a summary comment to the PR and (optionally) inline comments for important lines.
* CLI command to run the agent against a PR (so CI or local dev can call it).

**Enhancements (after MVP)**

* True inline comments using hunk position mapping for each provider.
* Security analyzer (Bandit, OWASP scans), complexity analysis, perf suggestions.
* Scoring system and a dashboard.
* CI integration and automatic pre-merge gating.
* Support for self-hosted git servers (via standard Git + patches).

---

## 2 — Architecture (high level)

```
+----------------+    +----------------+    +------------------+
|  Git Provider  | -> |  Adapters      | -> | PR Fetcher       |
| (GitHub/GitLab)|    | (github/gitlab)|    | (diff parser)    |
+----------------+    +----------------+    +------------------+
                                 |                    |
                                 v                    v
                         +----------------+    +------------------+
                         | Static Analyzers|   | AI Analyzer (LLM)|
                         | flake8, bandit |   | prompt templates | 
                         +----------------+    +------------------+
                                    \             /
                                     \           /
                                      v         v
                                     +-------------+
                                     | Reporter    |
                                     | (summary +  |
                                     | inline posts)|
                                     +-------------+
```

Key idea: everything communicates through small interfaces so you can swap implementations or add new provider adapters later.

---

## 3 — Repo layout (copy into your project root)

```
pr-review-agent/
├── README.md
├── PR-Review-Agent-Instructions.md   # this file
├── requirements.txt
├── pyproject.toml (optional)
├── docker-compose.yml (optional)
├── Dockerfile
├── src/
│   └── pr_agent/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base_adapter.py
│       │   ├── github_adapter.py
│       │   ├── gitlab_adapter.py   # stub
│       │   └── bitbucket_adapter.py # stub
│       ├── fetcher.py
│       ├── diff_parser.py
│       ├── analyzers/
│       │   ├── __init__.py
│       │   ├── static_analyzer.py
│       │   └── ai_analyzer.py
│       ├── reporter.py
│       └── server.py   # FastAPI webhook receiver (optional)
├── .github/workflows/pr-review.yml
└── tests/
    └── test_diff_parser.py
```

---

## 4 — `requirements.txt` (starter)

```
requests>=2.28
PyYAML
unidiff        # for parsing unified diffs
python-dotenv
Flask or FastAPI
pytest
pydantic
PyGithub       # optional but handy
python-gitlab  # optional
bandit         # for security scanning
flake8         # static lint
```

Add `eslint`, `mypy` etc. for polyglot projects (they are typically installed via npm or pip as appropriate).

---

## 5 — Environment variables & secrets

Create a `.env` (never commit this):

```
GEMINI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
GITLAB_TOKEN=glpat-...
BITBUCKET_USER=...
BITBUCKET_APP_PASSWORD=...
SERVICE_URL=https://your-agent.example.com  # optional webhook URL
```

Security: use least privileges for tokens (only repo\:repo scope or limited review scopes).

---

## 6 — Key implementation sketches (copy/paste friendly)

### 6.1 Base adapter interface (`base_adapter.py`)

```python
# src/pr_agent/adapters/base_adapter.py
from typing import Dict, List, Any

class BaseAdapter:
    """Adapter interface for a git hosting provider."""

    def get_pr(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        raise NotImplementedError

    def list_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Return unified diff text for the PR."""
        raise NotImplementedError

    def post_comment(self, owner: str, repo: str, pr_number: int, body: str) -> Any:
        raise NotImplementedError

    def post_inline_comment(self, owner: str, repo: str, pr_number: int, file_path: str, position: int, body: str) -> Any:
        raise NotImplementedError
```

### 6.2 GitHub adapter (minimal, using `requests`) — `github_adapter.py`

> This is a minimal example. For production, prefer `PyGithub` (handles pagination, GraphQL) or `gql` for GraphQL endpoints.

```python
# src/pr_agent/adapters/github_adapter.py
import os
import requests
from .base_adapter import BaseAdapter

GITHUB_API = "https://api.github.com"

class GitHubAdapter(BaseAdapter):
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({"Authorization": f"token {self.token}"})
        self.session.headers.update({"Accept": "application/vnd.github+json"})

    def get_pr(self, owner: str, repo: str, pr_number: int):
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
        r = self.session.get(url)
        r.raise_for_status()
        return r.json()

    def get_diff(self, owner: str, repo: str, pr_number: int) -> str:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
        r = self.session.get(url, headers={"Accept": "application/vnd.github.v3.diff"})
        r.raise_for_status()
        return r.text

    def list_files(self, owner: str, repo: str, pr_number: int):
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        r = self.session.get(url)
        r.raise_for_status()
        return r.json()

    def post_comment(self, owner: str, repo: str, pr_number: int, body: str):
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        r = self.session.post(url, json={"body": body})
        r.raise_for_status()
        return r.json()

    def post_inline_comment(self, owner: str, repo: str, pr_number: int, file_path: str, position: int, body: str):
        """
        position = patch position in the diff (1-based index of diff hunk lines) — see diff_parser helper.
        """
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        payload = {"body": body, "path": file_path, "position": position}
        r = self.session.post(url, json=payload)
        r.raise_for_status()
        return r.json()
```

Notes: GitHub accepts `position` (index in the unified diff). When using commit-based comments you can also supply `line` and `commit_id`.

### 6.3 Diff parser (`diff_parser.py`)

Use `unidiff` to parse unified diff text and map added lines to positions for inline comments.

```python
# src/pr_agent/diff_parser.py
from unidiff import PatchSet

class DiffParser:
    def __init__(self, diff_text: str):
        self.patch = PatchSet(diff_text)

    def files(self):
        for patched_file in self.patch:
            yield patched_file  # patched_file.path, patched_file.source_file, patched_file.target_file

    def get_added_line_positions(self):
        """Return mapping: {file_path: [(position, target_line_no, line_text), ...]}"""
        result = {}
        for patched_file in self.patch:
            file_path = patched_file.path
            positions = []
            pos = 0
            for hunk in patched_file:
                for line in hunk:
                    pos += 1
                    if line.is_added:
                        # unidiff line.target_line_no is the new file line number
                        positions.append((pos, line.target_line_no, line.value.strip('\n')))
            result[file_path] = positions
        return result
```

**Important:** `pos` above approximates `position` used by GitHub. For large or complex patches you must validate results. Some providers expect `line` numbers and `commit_id` instead.

### 6.4 Static analyzer wrapper (`static_analyzer.py`)

A simple wrapper that runs shell linters and collects results. Keep it pluggable so custom analyzers can be added.

```python
# src/pr_agent/analyzers/static_analyzer.py
import subprocess
from typing import List, Dict

class StaticAnalyzer:
    def run_flake8(self, repo_path: str) -> List[Dict]:
        # run flake8 and parse output (or use flake8 API)
        cmd = ["flake8", repo_path, "--format=%(path)s:%(row)d:%(col)d:%(code)s:%(text)s"]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode == 0:
            return []
        issues = []
        for line in out.stdout.splitlines():
            path, row, col, code, text = line.split(":", 4)
            issues.append({"path": path, "line": int(row), "col": int(col), "code": code, "text": text})
        return issues
```

### 6.5 AI Analyzer (`ai_analyzer.py`) — LLM-driven feedback

This wraps an LLM call and converts the model response into structured suggestions. Provide a prompt template that gives the model the diff and asks for a short JSON array of comments.

```python
# src/pr_agent/analyzers/ai_analyzer.py
import os
from typing import List, Dict
import openai

openai.api_key = os.environ.get("OPENAI_API_KEY")

PROMPT_TEMPLATE = """
You are a helpful, precise code reviewer.
I will supply a unified diff for a Pull Request and some context (language, files changed).
Return JSON: an array of suggestions, each with {{'file': str, 'position_hint': int|None, 'line': int|None, 'comment': str, 'severity': 'info'|'warning'|'error'}}.

Diff:
{diff}

Rules:
- Keep suggestions actionable and short (1-3 sentences).
- Prefer to include a code snippet when proposing replacements.
- If you cannot map to a position, set position_hint to null and include the file and line if known.

Return ONLY valid JSON.
"""

class AIAnalyzer:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model

    def analyze(self, diff_text: str) -> List[Dict]:
        prompt = PROMPT_TEMPLATE.format(diff=diff_text)
        # Use ChatCompletion for structured output
        resp = openai.ChatCompletion.create(
            model=self.model,
            messages=[{"role": "system", "content": "You are an expert code reviewer."},
                      {"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1200,
        )
        content = resp.choices[0].message.content.strip()
        # The model is asked to return JSON. Parse it.
        import json
        try:
            data = json.loads(content)
        except Exception:
            # If parsing fails, return a single generic comment
            return [{"file": None, "position_hint": None, "line": None, "comment": content, "severity": "warning"}]
        return data
```

**Notes:**

* Use `temperature=0` for deterministic outputs; if you want more creative suggestions increase it.
* Use a streaming approach for large PRs to avoid token limits (send only changed files or hunks instead of entire repo).

### 6.6 Reporter (summary + inline posts) — `reporter.py`

```python
# src/pr_agent/reporter.py
from typing import List

class Reporter:
    def __init__(self, adapter):
        self.adapter = adapter

    def post_summary(self, owner, repo, pr_number, summary_text: str):
        return self.adapter.post_comment(owner, repo, pr_number, summary_text)

    def post_inline_comments(self, owner, repo, pr_number, inline_items: List[dict]):
        results = []
        for it in inline_items:
            res = self.adapter.post_inline_comment(owner, repo, pr_number, it['file'], it['position'], it['comment'])
            results.append(res)
        return results
```

---

## 7 — CLI & local run (quick)

```python
# src/pr_agent/cli.py
import argparse
from pr_agent.adapters.github_adapter import GitHubAdapter
from pr_agent.fetcher import PRFetcher
from pr_agent.analyzers.ai_analyzer import AIAnalyzer
from pr_agent.reporter import Reporter

parser = argparse.ArgumentParser()
parser.add_argument('--provider', default='github')
parser.add_argument('--owner')
parser.add_argument('--repo')
parser.add_argument('--pr', type=int)
args = parser.parse_args()

adapter = GitHubAdapter()
fetcher = PRFetcher(adapter)
ai = AIAnalyzer()
reporter = Reporter(adapter)

pr_diff = adapter.get_diff(args.owner, args.repo, args.pr)
comments = ai.analyze(pr_diff)
# convert comments into summary + inline items
summary = """Automated review summary:\n"""
for c in comments:
    summary += f"- {c.get('file')}:{c.get('line')} — {c.get('comment')}\n"
reporter.post_summary(args.owner, args.repo, args.pr, summary)
```

Run locally with `python -m src.pr_agent.cli --owner myorg --repo myrepo --pr 12` (adjust to your entrypoint layout).

---

## 8 — CI Integration

**GitHub Actions example** (`.github/workflows/pr-review.yml`):

```yaml
name: PR Review (automated)
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  pr-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run PR agent
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python -m src.pr_agent.cli --provider github --owner ${{ github.repository_owner }} --repo ${{ github.event.repository.name }} --pr ${{ github.event.number }}
```

Notes: `GITHUB_TOKEN` grants repo-level permissions to post comments. For greater capabilities use a PAT.

---

## 9 — Using AI agents to implement modules (copy/paste prompts)

Below are *task prompts* you can give to an LLM (ChatGPT, Copilot, etc.) to generate code quickly. Paste a single prompt into an LLM with context (project layout) and ask it to create the file.

### Example prompt: Implement GitHub adapter

```
You are a Python backend engineer. Implement a file `src/pr_agent/adapters/github_adapter.py` that conforms to the following interface:
- class GitHubAdapter(BaseAdapter)
- methods: get_pr(owner, repo, pr_number), get_diff(owner, repo, pr_number), list_files(owner, repo, pr_number), post_comment(owner, repo, pr_number, body), post_inline_comment(owner, repo, pr_number, file_path, position, body)
- Use `requests` and environment variable `GITHUB_TOKEN` for authorization; raise exceptions on API errors; include docstrings and type hints.
- Keep the code <= 120 lines and include a small usage example in a `if __name__ == '__main__'` block.

Return only the Python file content with no extra commentary.
```

### Example prompt: Implement DiffParser

```
Implement `src/pr_agent/diff_parser.py` that exposes a `DiffParser` class which accepts unified diff text and has methods `files()` and `get_added_line_positions()` returning mapping file->list of (position, target_line_no, line_text). Use `unidiff` library. Return only the code.
```

### Example prompt: Implement AI analyzer (safeguard)

```
Implement `src/pr_agent/analyzers/ai_analyzer.py`. It must call the OpenAI ChatCompletion API (use `openai` lib) with a fixed prompt template. The method `analyze(diff_text)` should return parsed JSON: list of {file, position_hint, line, comment, severity}. Add robust JSON parsing and fallbacks. Keep code secure (read OPENAI_API_KEY from env). Return only the code.
```

Use the LLM iteratively: ask it to also generate unit tests for each module. You can run the generated tests in your environment to validate.

---

## 10 — Scoring system (simple, pluggable)

Create a `scorer.py` that accepts issues from static analyzers + AI suggestions and calculates a numeric score 0..100.

Scheme example (configurable):

* Linter issues: each -1 point (severity mapping)
* Security issues: -5 to -20 per issue
* AI warnings: -2 per medium
* No new tests: -5

Return a summary string and a machine-readable JSON report.

---

## 11 — Tests & Mocks

* Write unit tests for `diff_parser` with sample diffs (small ones).
* Mock adapter network responses using `responses` or `requests-mock`.
* Create an integration test that runs the agent against a local repo -- create a toy repo with two branches, generate a patch and feed it to the diff\_parser and analyzers.

---

## 12 — Dev environment (VS Code tips)

* Add a `.vscode/launch.json` that runs `src/pr_agent/cli.py` with args for debugging.
* Use a DevContainer / Dockerfile that installs Python, node (for linters), and `ngrok` if you want to test webhooks.

---

## 13 — Troubleshooting & gotchas

* **Line/position mapping:** Different providers use different semantics (`position` vs `line` vs `commit_id`). Start by posting summary comments first. Add inline comments only after validating mapping on a test PR.
* **Token scopes:** `GITHUB_TOKEN` provided in Actions can post comments; a PAT may be needed for more scopes.
* **Large PRs & tokens:** For huge diffs, send only changed files or hunk summaries to the LLM to avoid token limits.
* \*\*False
