from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "../templates"))


def get_auth_context(request: Request) -> dict:
    """Helper to get authentication context for templates"""
    return {
        "is_authenticated": getattr(request.state, "is_authenticated", False),
        "auth_enabled": getattr(request.state, "auth_enabled", False)
    }
