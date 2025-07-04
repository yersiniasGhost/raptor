from typing import Annotated
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from . import templates
from .hardware_deployment_route import get_hardware, HardwareDeploymentRoute
from hardware.electrak.actuator_manager import ActuatorManager
from hardware.gpio_controller.banner_alarm import BannerAlarm, BannerAlarmException

from utils import LogManager
logger = LogManager().get_logger(__name__)
router = APIRouter(prefix="/actuator", tags=["actuator"])


async def activate_warning_alarm(banner_alarm: BannerAlarm) -> None:
    """Activate warning alarm and wait for delay"""
    try:
        result = banner_alarm.activate_alarm("default")
        if result["status"] != "success":
            raise BannerAlarmException("Failed to activate alarm")

        # Wait for the warning period
        await asyncio.sleep(banner_alarm.DELAY_BETWEEN_LIGHTS_AND_ALARM)

    except Exception as e:
        logger.error(f"Error activating warning alarm: {e}")
        banner_alarm.deactivate_alarm()  # Cleanup on error
        raise BannerAlarmException(f"Failed to activate warning alarm: {str(e)}")


async def deactivate_warning_alarm(banner_alarm: BannerAlarm) -> None:
    """Deactivate warning alarm"""
    try:
        result = banner_alarm.deactivate_alarm()
        if result["status"] != "success":
            raise BannerAlarmException("Failed to deactivate alarm")
    except Exception as e:
        logger.error(f"Error deactivating warning alarm: {e}")
        raise BannerAlarmException(f"Failed to deactivate warning alarm: {str(e)}")


def get_actuators(deployment: HardwareDeploymentRoute) -> ActuatorManager:
    deployment.actuator_manager.reset_hardware()
    return deployment.actuator_manager


@router.get("/{actuator_id}/status")
async def get_actuator_status(actuator_id: str, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]) -> dict:
    actuator_manager = get_actuators(hardware)
    actuator = actuator_manager.get_actuator(actuator_id)
    if not actuator:
        raise HTTPException(status_code=404, detail="Actuator not found")

    try:
        status = actuator.current_state()
        if status['position'] == -90.0:
            logger.error(f"Could not get actuator current state: {status}")
            status = actuator.current_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if status is None:
        raise HTTPException(status_code=503, detail="Failed to read status")
    return status


@router.post("/{actuator_id}/move")
async def move_actuator(actuator_id: str, target_position: float = Form(...),
                        target_speed: float = Form(...), activate_alarm: bool = Form(False),
                        hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)] = None):
    """Move single actuator"""
    logger.info("Getting actuator.")
    manager = hardware.actuator_manager
    actuator = manager.get_actuator(actuator_id)
    if not actuator:
        raise HTTPException(status_code=404, detail="Actuator not found")
    try:
        success = await manager.move_one(actuator_id, target_position, target_speed, activate_alarm)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot move actuator: {str(e)}")

    if success:
        return {"message": f"Moving actuator {actuator_id}", "status": "success"}
    else:
        raise HTTPException(status_code=409, detail="Movement failed")


@router.post("/move-multiple")
async def move_multiple_actuators(target_position: float = Form(...),
                                  target_speed: float = Form(...), activate_alarm: bool = Form(False),
                                  hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)] = None):
    """Move multiple actuators simultaneously"""
    try:
        # Convert input format to manager format
        manager = hardware.actuator_manager
        success = await manager.move_multiple(target_position, target_speed)
        if success:
            return {
                "message": "Moving multiple actuators",
                "status": "commands_sent"
            }
        else:
            raise HTTPException(
                status_code=409,
                detail="One or more movements failed"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect", name="disconnect")
async def disconnect(request: Request, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        logger.info("Disconnecting Actuators")
        am = hardware.actuator_manager
        await am.cleanup()  # If cleanup is async
        return {"status": "disconnected"}
    except Exception as e:
        logger.error(f"Error during disconnect: {e}")
        return {"status": "error", "message": str(e)}



@router.get("/", name="actuator_index")
async def index(request: Request, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    logger.info("actuator index")
    am = get_actuators(hardware)
    if not am:
        return templates.TemplateResponse('hardware_not_configured.html',
                                          {"request": request,
                                           "hardware": "Actuator Controller"}
                                          )
    return templates.TemplateResponse(
        "actuators.html",
        {
            "request": request,
            "manager": am,
            "error": None
         }
    )
