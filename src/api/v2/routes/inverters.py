from typing import Annotated
from collections import deque
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from . import templates
from bms_store import BMSDataStore
from .hardware_deployment_route import HardwareDeploymentRoute, get_hardware
from utils import LogManager

logger = LogManager().get_logger("InverterRoute")
router = APIRouter(prefix="/inverters", tags=["inverters"])

# Load register map
try:
    # Initialize BMS data store
    bms_store = BMSDataStore()
    update_task = None
except Exception as e:
    logger.error(f"Failed to load Inverter configuration files: {e}")


def get_inverter(deployment: HardwareDeploymentRoute):
    return deployment.inverter


@router.get("/")
async def inverters(request: Request, deployment: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        hardware = get_inverter(deployment)
        if not hardware:
            return templates.TemplateResponse("no_hardware.html", {"system": "Inverters/Converters"})
        data = await bms_store.get_all_data()
        register_map = hardware.get_points("DATA")

        return templates.TemplateResponse(
            "inverters.html",
            {
                "hardware": hardware,
                "request": request,
                "data": data,
                "register_map": register_map,
                "error": None
            }
        )
    except Exception as e:
        logger.error(f"Error in Inverters route: {e}")
        return templates.TemplateResponse(
            "inverters.html",
            {
                "hardware": [],
                "request": request,
                "register_map": register_map,
                "error": str(e)
            }
        )


@router.get("/data")
async def get_inverter_data(deployment: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        hardware = get_inverter(deployment)
        values = hardware.data_acquisition()

        # Update each unit
        for device in hardware.devices:
            unit_id = device['mac']
            if isinstance(values, dict):  # Ensure values is a dictionary
                await bms_store.update_unit_data(unit_id, values[unit_id])
            else:
                logger.error(f"Unexpected values type: {type(values)}")
        data = await bms_store.get_all_data()

        return JSONResponse(content={"data": data, "error": None})
    except Exception as e:
        logger.error(f"Error getting Inverter data: {e}")
        return JSONResponse(content={"data": None, "error": str(e)})


@router.get("/historical/{unit_id}")
async def get_historical_data(unit_id: str, num_points: int = Query(default=800, ge=10, le=20000)):
    try:
        # battery = batteries.get_definition(unit_id)
        logger.info(f"Loading inverter historical data: {unit_id}")
        filename = f"inverter2_{unit_id}.csv"
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
