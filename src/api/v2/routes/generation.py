from collections import deque
from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from . import templates

from .hardware_deployment_route import HardwareDeploymentRoute, get_hardware
from bms_store import BMSDataStore

from utils import LogManager
logger = LogManager().get_logger("GenerationRoute")

router = APIRouter(prefix="/generation", tags=["generation"])
data_store = BMSDataStore()
GENERATION_SYSTEM = "PVCTs"


@router.get("/")
async def index(request: Request, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        # Update each unit
        hardware = hardware.pv_cts
        if not hardware:
            return templates.TemplateResponse('hardware_not_configured.html',
                                              {"request": request,
                                               "hardware": "PV Generation CT's"})

        hardware.get_identifiers()
        logger.info(f"Got Inverter identifiers")
        data = await data_store.get_all_data()
        register_map = hardware.get_points("DATA")
        logger.info(f"GET CT's: {hardware.hardware_id}, devices: {len(hardware.devices)}")
        logger.info(f"CT DATA registers: {register_map}  ")

        return templates.TemplateResponse(
            "generation.html",
            {
                "hardware": hardware,
                "request": request,
                "data": data,
                "register_map": register_map,
                "error": None
            }
        )
    except Exception as e:
        logger.error(f"{e}", exc_info=True)
        return templates.TemplateResponse(
            "generation.html",
            {
                "hardware": [],
                "request": request,
                "register_map": {},
                "error": str(e)
            }
        )

@router.get("/historical/{unit_id}")
async def get_historical_data(unit_id: str, num_points: int = Query(default=800, ge=10, le=20000)):
    try:
        # battery = batteries.get_definition(unit_id)
        logger.info(f"Loading Generation CTs historical data: {unit_id}")
        filename = f"{GENERATION_SYSTEM}_{unit_id}.csv"
        last_points = deque(maxlen=num_points)
        with open(filename, 'r') as file:
            header = file.readline().strip()
            for line in file:
                last_points.append(line)
        logger.info(f"DEBUG: got {len(last_points)} points.  Header: {header}")
        csv_data = header + '\n' + '\n'.join(last_points)
        return JSONResponse(content={"data": csv_data, "error": None})

    except FileNotFoundError:
        logger.error(f"CSV file not found for unit {unit_id}")
        return JSONResponse(content={"data": None, "error": f"No historical data found for unit {unit_id}"})
    except Exception as e:
        logger.error(f"Error reading historical data for unit {unit_id}: {e}")
        return JSONResponse(content={"data": None, "error": str(e)})


@router.get("/data")
async def get_test_data(hardware_def: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    cts = hardware_def.pv_cts
    if not cts:
        return JSONResponse(content={ "data": None, "error": "Not configured" })

    values = cts.hardware.test_device(cts.devices[0])
    return { "success": True, "value": values}
