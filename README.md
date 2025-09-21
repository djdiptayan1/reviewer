# PR Review Agent

An AI-powered agent for reviewing Pull Requests across multiple git servers (GitHub, GitLab, Bitbucket). The system analyzes code changes, runs static analysis, provides AI-driven feedback, and posts comprehensive reviews with inline comments.

## Features

- **Multi-Platform Support**: Works with GitHub, GitLab, and Bitbucket
- **AI-Powered Analysis**: Uses Google Gemini models for intelligent code review
- **Static Analysis**: Integrated linters (flake8, ESLint, bandit, etc.)
- **Security Scanning**: Built-in security pattern detection
- **Inline Comments**: Posts feedback directly on relevant code lines
- **Comprehensive Reports**: Detailed summary comments with statistics
- **Configurable**: Flexible configuration via YAML files and environment variables
- **Modular Architecture**: Easy to extend with new analyzers and adapters

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd reviewer

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file with your API keys:

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

Required environment variables:

- `GITHUB_TOKEN`: GitHub personal access token
- `GEMINI_API_KEY`: Google Gemini API key for AI analysis
- `GITLAB_TOKEN`: GitLab token (if using GitLab)

### 3. Basic Usage

Review a GitHub PR:
```bash
python -m src.pr_agent.cli --provider github --owner myorg --repo myrepo --pr 123
```

Review with custom options:
```bash
python -m src.pr_agent.cli --provider github --owner myorg --repo myrepo --pr 123 \
  --no-inline --ai-model gpt-4 --max-comments 10
```

Dry run (analyze without posting):
```bash
python -m src.pr_agent.cli --provider github --owner myorg --repo myrepo --pr 123 --dry-run
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_TOKEN` | GitHub personal access token | Yes (for GitHub) |
| `GITLAB_TOKEN` | GitLab access token | Yes (for GitLab) |
| `OPENAI_API_KEY` | OpenAI API key | Yes (for AI analysis) |
| `DEFAULT_AI_MODEL` | OpenAI model to use | No (defaults to gpt-4o-mini) |
| `MAX_DIFF_SIZE` | Maximum diff size to analyze | No (defaults to 50000) |
| `ENABLE_INLINE_COMMENTS` | Enable inline comments | No (defaults to true) |

### Configuration File

Generate a sample configuration file:
```bash
python -m src.pr_agent.cli --generate-config config.yaml
```

Validate your configuration:
```bash
python -m src.pr_agent.cli --validate-config
```

## Architecture

```
pr_agent/
├── adapters/          # Git server adapters (GitHub, GitLab, etc.)
├── analyzers/         # Code analyzers (static, AI)
├── cli.py            # Command-line interface
├── config.py         # Configuration management
├── diff_parser.py    # Diff parsing and analysis
└── reporter.py       # Comment formatting and posting
```

### Key Components

- **Adapters**: Abstract interface for different git servers
- **Analyzers**: Static analysis and AI-powered code review
- **Diff Parser**: Unified diff parsing and line mapping
- **Reporter**: Comment formatting and posting
- **Config Manager**: Centralized configuration handling

## Static Analysis Tools

The agent automatically runs appropriate static analysis tools based on file types:

- **Python**: flake8, bandit (security), mypy (optional)
- **JavaScript/TypeScript**: ESLint
- **Security**: Pattern-based security checks
- **General**: Code complexity and maintainability checks

## AI Analysis

The AI analyzer uses OpenAI models to provide intelligent feedback on:

- Code quality and maintainability
- Potential bugs and logic errors
- Security vulnerabilities
- Performance improvements
- Best practices and conventions
- Architecture and design patterns

## Command Line Options

```
usage: cli.py [-h] [--provider {github,gitlab,bitbucket}] [--owner OWNER] 
              [--repo REPO] [--pr PR] [--config CONFIG] [--validate-config]
              [--generate-config GENERATE_CONFIG] [--no-ai] [--no-static]
              [--ai-model AI_MODEL] [--confidence-threshold FLOAT]
              [--no-inline] [--no-summary] [--max-comments N] [--dry-run]
              [--verbose] [--debug] [--json] [--output OUTPUT]

AI-powered PR Review Agent

PR Review Arguments:
  --provider {github,gitlab,bitbucket}
                        Git server provider
  --owner OWNER         Repository owner/organization
  --repo REPO          Repository name
  --pr PR              Pull request number

Configuration:
  --config CONFIG      Path to configuration file (YAML format)
  --validate-config    Validate configuration and exit
  --generate-config GENERATE_CONFIG
                        Generate sample configuration file and exit

Analysis Options:
  --no-ai              Disable AI-powered analysis
  --no-static          Disable static analysis
  --ai-model AI_MODEL  OpenAI model to use for AI analysis
  --confidence-threshold FLOAT
                        Minimum confidence threshold for AI feedback (0.0-1.0)

Review Options:
  --no-inline          Disable inline comments, only post summary
  --no-summary         Disable summary comment, only post inline comments
  --max-comments N     Maximum number of inline comments to post
  --dry-run            Perform analysis but don't post comments

Output Options:
  --verbose, -v        Enable verbose output
  --debug              Enable debug output
  --json               Output results in JSON format
  --output OUTPUT      Save results to file
```

## Examples

### Review with AI only
```bash
python -m src.pr_agent.cli --provider github --owner myorg --repo myrepo --pr 123 --no-static
```

### Security-focused review
```bash
python -m src.pr_agent.cli --provider github --owner myorg --repo myrepo --pr 123 \
  --ai-model gpt-4 --confidence-threshold 0.8
```

### Analyze without posting
```bash
python -m src.pr_agent.cli --provider github --owner myorg --repo myrepo --pr 123 \
  --dry-run --verbose --output review-results.json
```

## Integration

### GitHub Actions

Create `.github/workflows/pr-review.yml`:

```yaml
name: PR Review
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
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
      - name: Run PR Review Agent
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python -m src.pr_agent.cli --provider github \
            --owner ${{ github.repository_owner }} \
            --repo ${{ github.event.repository.name }} \
            --pr ${{ github.event.number }}
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
pr-review:
  stage: test
  image: python:3.11
  script:
    - pip install -r requirements.txt
    - python -m src.pr_agent.cli --provider gitlab --owner $CI_PROJECT_NAMESPACE --repo $CI_PROJECT_NAME --pr $CI_MERGE_REQUEST_IID
  only:
    - merge_requests
  variables:
    GITLAB_TOKEN: $GITLAB_TOKEN
    OPENAI_API_KEY: $OPENAI_API_KEY
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## Security

- API keys are loaded from environment variables
- Tokens should have minimal required permissions
- Review output is posted using the configured git server APIs
- No code or sensitive data is sent to external services except OpenAI

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Troubleshooting

### Common Issues

**Invalid credentials**: Ensure your API tokens have the correct permissions:
- GitHub: `repo` scope for private repos, `public_repo` for public repos
- GitLab: `api` scope
- OpenAI: Valid API key with sufficient credits

**Large diffs**: For very large PRs, the tool may skip analysis. Increase `MAX_DIFF_SIZE` or split the PR.

**Rate limits**: If you hit API rate limits, wait or use tokens with higher limits.

**Missing tools**: Install static analysis tools:
```bash
pip install flake8 bandit
npm install -g eslint  # for JavaScript analysis
```

### Debug Mode

Run with `--debug` for detailed error information:
```bash
python -m src.pr_agent.cli --provider github --owner myorg --repo myrepo --pr 123 --debug
```