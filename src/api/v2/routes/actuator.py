from fastapi import APIRouter, Request
from . import templates
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/actuator", tags=["actuator"])


async def route_setup():
    logger.info("HERE in route setup")
    yield


@router.get("/", name="actuator_index")
async def index(request: Request):
    return templates.TemplateResponse(
        "actuators.html",
        {"request": request}
    )
