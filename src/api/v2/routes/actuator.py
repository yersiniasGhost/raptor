from fastapi import APIRouter, Request
from . import templates

router = APIRouter(prefix="/actuator", tags=["actuator"])


@router.get("/", name="actuator_index")
async def index(request: Request):
    return templates.TemplateResponse(
        "actuators.html",
        {"request": request}
    )
