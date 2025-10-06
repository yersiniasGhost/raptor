from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse
from . import templates, get_auth_context
from utils import LogManager

logger = LogManager().get_logger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/")
async def bms(request: Request):
    try:
        return templates.TemplateResponse(
            "analysis.html",
            {
                "request": request,
                "error": None,
                **get_auth_context(request)
            }
        )
    except Exception as e:
        logger.error(f"Error in Analysis route: {e}")
        return templates.TemplateResponse(
            "analysis.html",
            {
                "request": request,
                "error": str(e),
                **get_auth_context(request)
            }
        )
