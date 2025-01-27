from typing import Annotated
from fastapi import APIRouter, Request, Depends, HTTPException
from . import templates
import logging
from .hardware_deployment import get_hardware, HardwareDeployment
from communications.electrak.actuator_manager import ActuatorManager


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/actuator", tags=["actuator"])


def get_actuators(deployment: HardwareDeployment) -> ActuatorManager:
    return deployment.actuator_manager


@router.get("/{actuator_id}/status")
async def get_actuator_status(actuator_id: str, hardware: Annotated[HardwareDeployment, Depends(get_hardware)]) -> dict:
    actuator_manager = get_actuators(hardware)
    actuator = actuator_manager.get_actuator(actuator_id)
    if not actuator:
        raise HTTPException(status_code=404, detail="Actuator not found")

    try:
        status = actuator.current_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if status is None:
        raise HTTPException(status_code=503, detail="Failed to read status")
    return status


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
