# Render Configuration for PR Review Agent

## Build Command
```bash
pip install -r requirements.txt
```

## Start Command  
```bash
python -m uvicorn src.pr_agent.web_api:app --host 0.0.0.0 --port $PORT
```

## Environment Variables (Set in Render Dashboard)

### Required
- `GITHUB_TOKEN` - GitHub personal access token
- `GEMINI_API_KEY` - Google Gemini API key

### Optional
- `GITLAB_TOKEN` - GitLab access token (if using GitLab)
- `BITBUCKET_USERNAME` - Bitbucket username (if using Bitbucket)
- `BITBUCKET_APP_PASSWORD` - Bitbucket app password (if using Bitbucket)
- `PORT` - Port to run on (Render sets this automatically)
- `HOST` - Host to bind to (defaults to 0.0.0.0)

## API Endpoints

### Health Check
- `GET /` or `GET /health` - Service health status
- `GET /config` - Configuration validation status
- `GET /providers` - Available git server providers
- `GET /models` - Available AI models

### Review PR
- `POST /review` - Analyze a pull request

Example request:
```json
{
  "provider": "github",
  "owner": "username",
  "repo": "repository", 
  "pr": 123,
  "dry_run": true,
  "post_inline": true,
  "post_summary": true
}
```

### Interactive Documentation
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation

## Deployment Steps

1. **Create Render Account** - Sign up at render.com
2. **Connect Repository** - Link your GitHub repository
3. **Configure Service**:
   - Service Type: Web Service
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python -m uvicorn src.pr_agent.web_api:app --host 0.0.0.0 --port $PORT`
4. **Set Environment Variables** - Add all required tokens in Render dashboard
5. **Deploy** - Render will automatically build and deploy

## Usage Examples

### Health Check
```bash
curl https://your-app.onrender.com/health
```

### Review a PR (Dry Run)
```bash
curl -X POST https://your-app.onrender.com/review \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "github",
    "owner": "microsoft", 
    "repo": "vscode",
    "pr": 123,
    "dry_run": true
  }'
```

### Review and Post Comments
```bash
curl -X POST https://your-app.onrender.com/review \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "github",
    "owner": "your-org",
    "repo": "your-repo", 
    "pr": 456,
    "dry_run": false,
    "post_inline": true,
    "post_summary": true
  }'
```

## Features

✅ **Multi-Platform Support** - GitHub, GitLab, Bitbucket
✅ **AI-Powered Analysis** - Google Gemini integration  
✅ **Static Analysis** - flake8, bandit, and more
✅ **Code Quality Scoring** - Comprehensive scoring system
✅ **Professional Output** - Clean, emoji-free reports
✅ **Detailed Feedback** - Explanations and fix suggestions
✅ **REST API** - Easy integration with CI/CD pipelines
✅ **Interactive Docs** - Built-in API documentation

## Security Notes

- All API keys should be set as environment variables in Render
- The service validates credentials before processing requests
- Dry run mode is available for testing without posting comments
- CORS is enabled for web client integration