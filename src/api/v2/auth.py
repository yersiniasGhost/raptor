"""
Authentication module for VMC-UI

Provides session-based authentication using environment variable.
Supports both plain text (VMC_PASSWORD) and hashed (VMC_PASSWORD_HASH).
"""
import os
import hashlib
import secrets
from typing import Optional
from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from utils import LogManager

logger = LogManager().get_logger("VMC-Auth")

# Session management - simple in-memory sessions
_active_sessions = set()


def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def get_password_hash_from_env() -> Optional[str]:
    """Get password hash from VMC_PASSWORD_HASH environment variable"""
    return os.environ.get("VMC_PASSWORD_HASH")


def get_password_from_env() -> Optional[str]:
    """Get plain text password from VMC_PASSWORD (legacy/fallback)"""
    return os.environ.get("VMC_PASSWORD")


def create_session(request: Request) -> str:
    """Create a new session for authenticated user"""
    session_token = secrets.token_urlsafe(32)
    _active_sessions.add(session_token)
    return session_token


def validate_session(request: Request) -> bool:
    """Check if the request has a valid session"""
    session_token = request.cookies.get("session_token")
    return session_token in _active_sessions if session_token else False


def destroy_session(request: Request):
    """Destroy a session (logout)"""
    session_token = request.cookies.get("session_token")
    if session_token and session_token in _active_sessions:
        _active_sessions.discard(session_token)


def verify_password(password: str) -> bool:
    """
    Verify password against environment variable.
    Checks VMC_PASSWORD_HASH first (preferred), then VMC_PASSWORD (fallback).
    """
    # Check for hashed password first (preferred)
    env_hash = get_password_hash_from_env()
    if env_hash:
        return hash_password(password) == env_hash

    # Fallback to plain text password for backward compatibility
    env_password = get_password_from_env()
    if env_password:
        logger.warning("Using plain text VMC_PASSWORD. Consider using VMC_PASSWORD_HASH instead.")
        return password == env_password

    return False


def is_password_set() -> bool:
    """Check if a password has been configured in environment"""
    return get_password_hash_from_env() is not None or get_password_from_env() is not None


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce authentication on all routes except login"""

    # Routes that don't require authentication
    PUBLIC_PATHS = {"/login", "/static"}

    async def dispatch(self, request: Request, call_next):
        # Store authentication status in request state for templates
        request.state.is_authenticated = validate_session(request)
        request.state.auth_enabled = is_password_set()

        # Allow static files and public paths
        if any(request.url.path.startswith(path) for path in self.PUBLIC_PATHS):
            return await call_next(request)

        # Check if password is configured
        if not is_password_set():
            # If no password set, allow access without authentication
            logger.warning("No VMC_PASSWORD environment variable set - running without authentication")
            return await call_next(request)

        # Check if user is authenticated
        if not request.state.is_authenticated:
            # Redirect to login if not authenticated
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)
