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
from bms_store import BMSDataStore

from utils import LogManager
logger = LogManager().get_logger(__name__)

router = APIRouter(prefix="/bms", tags=["bms"])
bms_store = BMSDataStore()
CC_TEMPLATE = "charge_controller_template.html"


def get_charge_controller(deployment: HardwareDeploymentRoute) -> HardwareDeployment:
    return deployment.charge_controller


@router.get("/data")
async def get_bms_data(hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        # Update each unit
        cc = get_charge_controller(hardware)
        values = cc.data_acquisition()
        for device in cc.devices:
            unit_id = device["mac"]
            if isinstance(values, dict):  # Ensure values is a dictionary
                await bms_store.update_unit_data(unit_id, values[unit_id])
            else:
                logger.error(f"Unexpected values type: {type(values)}")
        data = await bms_store.get_all_data()
        # Now grab the trend data and calculate that fun!
        return JSONResponse(content={"data": data, "error": None})
    except Exception as e:
        logger.error(f"Error getting BMS data: {e}", exc_info=True)
        return JSONResponse(content={"data": None, "error": str(e)})


@router.get("/historical/{unit_id}")
async def get_historical_data(unit_id: str, num_points: int = Query(default=4000, ge=100, le=10000)):
    try:
        filename = f"ChargeController_{unit_id}.csv"
        last_points = deque(maxlen=num_points)
        with open(filename, 'r') as file:
            header = file.readline().strip()
            for line in file:
                last_points.append(line)

        csv_data = header + '\n' + '\n'.join(last_points)
        return JSONResponse(content={"data": csv_data, "error": None})
    except FileNotFoundError:
        logger.error(f"CSV file not found for unit {unit_id}")
        return JSONResponse(content={"data": None, "error": f"No historical data found for unit {unit_id}"})
    except Exception as e:
        logger.error(f"Error reading historical data for unit {unit_id}: {e}")
        return JSONResponse(content={"data": None, "error": str(e)})


@router.get("/")
async def charge(request: Request, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    charge_controller = get_charge_controller(hardware)
    charge_controller.get_identifiers()
    register_map = charge_controller.get_points("DATA")
    try:
        bms_data = await bms_store.get_all_data()
        return templates.TemplateResponse(
            CC_TEMPLATE,
            {
                "charge_controller": charge_controller,
                "request": request,
                "charge_data": bms_data,
                "register_map": register_map,
                "error": None
            }
        )
    except Exception as e:
        logger.error(f"Error in BMS route: {e}")
        return templates.TemplateResponse(
            CC_TEMPLATE,
            {
                "charge_controller": None,
                "request": request,
                "bms_data": {},
                "register_map": None,
                "error": str(e)
            }
        )
