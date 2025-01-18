from fastapi import APIRouter, Request
from . import templates

router = APIRouter(prefix="/actuator", tags=["actuator"])


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        "actuator/index.html",
        {"request": request}
    )
