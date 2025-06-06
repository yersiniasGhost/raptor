import subprocess
from datetime import datetime
from typing import Tuple, Optional, List, Dict
from typing import Annotated
from collections import deque
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from . import templates

from hardware.hardware_deployment import HardwareDeployment
from .hardware_deployment_route import HardwareDeploymentRoute, get_hardware

from utils import LogManager
logger = LogManager().get_logger("GenerationRoute")

router = APIRouter(prefix="/generation", tags=["generation"])


@router.get("/")
async def generation_data(request: Request, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        # Update each unit
        cts = hardware.pv_cts
        return templates.TemplateResponse(
            "generation.html",
            {
                "request": request,
                "cts": cts
            }
        )
    except Exception as e:
        logger.error(f"{e}",exc_info=True)


@router.get("/data")
async def get_test_data(hardware_def: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    cts = hardware_def.pv_cts
    if not cts:
        values = {}
    else:
        values = cts.hardware.test_device(cts.devices[0])
    return { "success": True, "value": values}
