"""
FastAPI web service wrapper for the PR Review Agent.

This module provides a REST API interface for the PR Review Agent,
making it deployable as a web service on platforms like Render.
"""

import os
import sys
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Add the src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pr_agent.config import ConfigManager
from pr_agent.adapters.github_adapter import GitHubAdapter
from pr_agent.adapters.gitlab_adapter import GitLabAdapter
from pr_agent.diff_parser import DiffParser
from pr_agent.analyzers.static_analyzer import StaticAnalyzer
from pr_agent.analyzers.ai_analyzer import AIAnalyzer
from pr_agent.reporter import Reporter

# Initialize FastAPI app
app = FastAPI(
    title="PR Review Agent API",
    description="AI-powered code review service for GitHub, GitLab, and Bitbucket pull requests",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global configuration
config_manager = None
config = None

# Request/Response Models
class ReviewRequest(BaseModel):
    """Request model for PR review."""
    provider: str = Field(..., description="Git server provider (github, gitlab, bitbucket)")
    owner: str = Field(..., description="Repository owner/organization")
    repo: str = Field(..., description="Repository name") 
    pr: int = Field(..., description="Pull request number", gt=0)
    dry_run: bool = Field(True, description="If true, analyze but don't post comments")
    post_inline: bool = Field(True, description="Whether to post inline comments")
    post_summary: bool = Field(True, description="Whether to post summary comment")
    ai_model: Optional[str] = Field(None, description="AI model to use (overrides config)")
    max_comments: Optional[int] = Field(None, description="Maximum inline comments to post")


class ReviewResponse(BaseModel):
    """Response model for PR review."""
    status: str = Field(..., description="Status: success, error, or partial")
    request_id: str = Field(..., description="Unique request identifier")
    summary: Dict[str, Any] = Field(..., description="Review summary statistics")
    quality_score: Optional[Dict[str, int]] = Field(None, description="Code quality scoring")
    ai_summary: Optional[str] = Field(None, description="AI-generated summary")
    issues_found: int = Field(..., description="Total issues found")
    static_issues: int = Field(..., description="Static analysis issues")
    ai_feedback_items: int = Field(..., description="AI feedback items")
    comments_posted: Optional[int] = Field(None, description="Number of comments posted")
    errors: List[str] = Field(default=[], description="Any errors that occurred")
    processing_time: float = Field(..., description="Processing time in seconds")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str
    services: Dict[str, str]


class ConfigResponse(BaseModel):
    """Configuration status response."""
    valid: bool
    errors: List[str] = []
    providers_available: List[str] = []


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize configuration on startup."""
    global config_manager, config
    try:
        config_manager = ConfigManager()
        config = config_manager.load_config()
        print("PR Review Agent API started successfully")
    except Exception as e:
        print(f"Failed to initialize configuration: {e}")
        # Continue anyway for health checks


# Health check endpoint
@app.get("/", response_model=HealthResponse)
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    services = {}
    
    # Check GitHub token
    if os.getenv("GITHUB_TOKEN"):
        services["github"] = "available"
    else:
        services["github"] = "no_token"
    
    # Check GitLab token  
    if os.getenv("GITLAB_TOKEN"):
        services["gitlab"] = "available"
    else:
        services["gitlab"] = "no_token"
        
    # Check Gemini API key
    if os.getenv("GEMINI_API_KEY"):
        services["gemini"] = "available"
    else:
        services["gemini"] = "no_token"
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        services=services
    )


# Configuration validation endpoint
@app.get("/config", response_model=ConfigResponse)
async def validate_config():
    """Validate configuration and return status."""
    global config_manager, config
    
    if not config_manager:
        try:
            config_manager = ConfigManager()
            config = config_manager.load_config()
        except Exception as e:
            return ConfigResponse(
                valid=False,
                errors=[f"Failed to load configuration: {str(e)}"]
            )
    
    try:
        errors = config_manager.validate_config()
        providers = []
        
        # Check which providers are available
        if os.getenv("GITHUB_TOKEN"):
            providers.append("github")
        if os.getenv("GITLAB_TOKEN"):
            providers.append("gitlab")
        if os.getenv("BITBUCKET_USERNAME") and os.getenv("BITBUCKET_APP_PASSWORD"):
            providers.append("bitbucket")
            
        return ConfigResponse(
            valid=len(errors) == 0,
            errors=errors,
            providers_available=providers
        )
    except Exception as e:
        return ConfigResponse(
            valid=False,
            errors=[f"Configuration validation failed: {str(e)}"]
        )


# Main review endpoint
@app.post("/review", response_model=ReviewResponse)
async def review_pr(request: ReviewRequest, background_tasks: BackgroundTasks):
    """
    Analyze a pull request and optionally post review comments.
    
    This endpoint performs comprehensive code review including:
    - Static analysis (flake8, bandit, etc.)
    - AI-powered analysis using Google Gemini
    - Code quality scoring
    - Inline and summary comment posting
    """
    start_time = datetime.now()
    request_id = f"{request.provider}-{request.owner}-{request.repo}-{request.pr}-{int(start_time.timestamp())}"
    
    try:
        # Validate configuration
        global config_manager, config
        if not config_manager or not config:
            config_manager = ConfigManager()
            config = config_manager.load_config()
        
        # Get appropriate adapter
        adapter = _get_adapter(request.provider)
        if not adapter:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported provider: {request.provider}"
            )
        
        if not adapter.validate_credentials():
            raise HTTPException(
                status_code=401,
                detail=f"Invalid credentials for {request.provider}"
            )
        
        # Get PR information
        pr_info = adapter.get_pr_info(request.owner, request.repo, request.pr)
        if not pr_info:
            raise HTTPException(
                status_code=404,
                detail=f"PR {request.pr} not found in {request.owner}/{request.repo}"
            )
        
        # Get PR diff
        diff_text = adapter.get_pr_diff(request.owner, request.repo, request.pr)
        if not diff_text.strip():
            return ReviewResponse(
                status="success",
                request_id=request_id,
                summary={"message": "No changes found in PR"},
                issues_found=0,
                static_issues=0,
                ai_feedback_items=0,
                processing_time=(datetime.now() - start_time).total_seconds()
            )
        
        # Parse diff for analysis
        diff_parser = DiffParser(diff_text)
        stats = diff_parser.get_stats()
        
        # Check diff size
        if (stats["additions"] + stats["deletions"]) > config.review.max_diff_size:
            raise HTTPException(
                status_code=413,
                detail=f"Diff too large ({stats['additions'] + stats['deletions']} changes, max {config.review.max_diff_size})"
            )
        
        # Run static analysis
        static_issues = []
        if config.analyzers.flake8_enabled:
            static_analyzer = StaticAnalyzer()
            files = diff_parser.get_files()
            
            # Analyze files (simplified for API)
            for file_path in files:
                file_analysis = diff_parser.get_file_analysis(file_path)
                if file_analysis and file_path.endswith('.py'):
                    # Basic content analysis for demo
                    content = "\n".join([
                        change.line_content for change in file_analysis.line_changes
                        if change.change_type == "add"
                    ])
                    if content.strip():
                        issues = static_analyzer.analyze_content(content, file_path)
                        static_issues.extend(issues)
        
        # Run AI analysis
        ai_feedback = []
        quality_score = None
        ai_summary = None
        
        if config.analyzers.ai_enabled:
            ai_analyzer = AIAnalyzer(
                model=request.ai_model or config.analyzers.ai_model,
                api_key=config.gemini_api_key,
            )
            
            pr_metadata = {
                "title": pr_info.title,
                "description": pr_info.description,
                "author": pr_info.author,
            }
            
            ai_feedback, quality_score, ai_summary = ai_analyzer.analyze_diff(diff_text, pr_metadata)
            
            # Filter by confidence threshold
            if config.review.min_confidence_threshold > 0:
                ai_feedback = [
                    feedback for feedback in ai_feedback
                    if feedback.confidence >= config.review.min_confidence_threshold
                ]
        
        # Post review if not dry run
        comments_posted = None
        post_errors = []
        
        if not request.dry_run:
            reporter = Reporter(adapter)
            
            pr_metadata = {
                "title": pr_info.title,
                "description": pr_info.description,
                "author": pr_info.author,
            }
            
            results = reporter.post_review(
                owner=request.owner,
                repo=request.repo,
                pr_number=request.pr,
                static_issues=static_issues,
                ai_feedback=ai_feedback,
                pr_info=pr_metadata,
                post_inline=request.post_inline,
                post_summary=request.post_summary,
                quality_score=quality_score,
                ai_summary=ai_summary,
            )
            
            comments_posted = results.get("inline_comments", 0)
            post_errors = results.get("errors", [])
        
        # Prepare response
        processing_time = (datetime.now() - start_time).total_seconds()
        
        response = ReviewResponse(
            status="success" if not post_errors else "partial",
            request_id=request_id,
            summary={
                "pr_title": pr_info.title,
                "author": pr_info.author,
                "files_changed": stats["files"],
                "additions": stats["additions"],
                "deletions": stats["deletions"],
                "total_changes": stats["additions"] + stats["deletions"]
            },
            quality_score={
                "overall": quality_score.overall,
                "security": quality_score.security,
                "performance": quality_score.performance,
                "maintainability": quality_score.maintainability,
                "architecture": quality_score.architecture,
                "testing": quality_score.testing,
                "documentation": quality_score.documentation
            } if quality_score else None,
            ai_summary=ai_summary,
            issues_found=len(static_issues) + len(ai_feedback),
            static_issues=len(static_issues),
            ai_feedback_items=len(ai_feedback),
            comments_posted=comments_posted,
            errors=post_errors,
            processing_time=processing_time
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "request_id": request_id,
                "processing_time": processing_time
            }
        )


# Helper function to get adapter
def _get_adapter(provider: str):
    """Get the appropriate adapter for the provider."""
    global config
    
    if provider == "github":
        git_config = config.git_servers.github
        return GitHubAdapter(token=git_config.token, api_url=git_config.api_url)
    elif provider == "gitlab":
        git_config = config.git_servers.gitlab
        return GitLabAdapter(token=git_config.token, api_url=git_config.api_url)
    # Add bitbucket when implemented
    
    return None


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with proper error response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error",
            "details": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )


# Additional utility endpoints
@app.get("/providers")
async def list_providers():
    """List available git server providers."""
    providers = []
    
    if os.getenv("GITHUB_TOKEN"):
        providers.append({
            "name": "github",
            "status": "available",
            "description": "GitHub integration"
        })
    
    if os.getenv("GITLAB_TOKEN"):
        providers.append({
            "name": "gitlab", 
            "status": "available",
            "description": "GitLab integration"
        })
        
    if os.getenv("BITBUCKET_USERNAME") and os.getenv("BITBUCKET_APP_PASSWORD"):
        providers.append({
            "name": "bitbucket",
            "status": "available", 
            "description": "Bitbucket integration"
        })
    
    return {"providers": providers}


@app.get("/models")
async def list_ai_models():
    """List available AI models."""
    return {
        "models": [
            {
                "name": "gemini-1.5-flash",
                "provider": "google",
                "description": "Fast and efficient model for code review",
                "default": True
            },
            {
                "name": "gemini-1.5-pro", 
                "provider": "google",
                "description": "More capable model for complex analysis"
            }
        ]
    }


# Run the app
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "web_api:app",
        host=host,
        port=port,
        reload=False,
        access_log=True
    )