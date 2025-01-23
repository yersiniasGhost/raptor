from typing import Annotated
from fastapi import APIRouter, Request, Depends
from . import templates
import logging
from .hardware_deployment import get_hardware, HardwareDeployment
from communications.electrak.actuator_manager import ActuatorManager


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/actuator", tags=["actuator"])


def get_actuators(deployment: HardwareDeployment) -> ActuatorManager:
    return deployment.actuator_manager


@router.get("/", name="actuator_index")
async def index(request: Request, hardware: Annotated[HardwareDeployment, Depends(get_hardware)]):
    am = get_actuators(hardware)
    return templates.TemplateResponse(
        "actuators.html",
        {
            "request": request,
            "manager": am,
            "error": None
         }
    )
