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
async def generation_data(hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        # Update each unit
        cts = hardware.generation_cts
        values = cts.data_acquisition()
        for device in cts.devices:
            unit_id = device["mac"]
            trend_data = {
                "trend": trend,
                "time-to-go": time_to_go,
                "soc-1hr": soc_1hr,
                "soc-2hr": soc_2hr
            }
            if isinstance(values, dict):  # Ensure values is a dictionary
                await bms_store.update_unit_data(unit_id, values[unit_id])
                await bms_store.add_unit_data(unit_id, trend_data)
            else:
                logger.error(f"Unexpected values type: {type(values)}")
        data = await bms_store.get_all_data()

        # Now grab the trend data and calculate that fun!
        return JSONResponse(content={"data": data, "error": None})
    except Exception as e:
        logger.error(f"Error getting BMS data: {e}", exc_info=True)
        return JSONResponse(content={"data": None, "error": str(e)})
