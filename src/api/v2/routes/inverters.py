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
INVERTER_SYSTEM = "Converters"

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
    hardware = get_inverter(deployment)

    if not hardware:
        return templates.TemplateResponse('hardware_not_configured.html',
                                          {"request": request,
                                           "hardware": "Inverters/Converters"}
                                          )
    try:

        hardware.get_identifiers()
        logger.info(f"Got Inverter identifiers")
        data = await bms_store.get_all_data()
        modbus_map = hardware.get_modbus_maps()
        register_map = modbus_map.get("DATA", {})
        has_ac_input = hardware.has_input_AC(hardware.devices)
        hardware.scenario_status("no mode")

        logger.info(f"GET inverters: {hardware.hardware_id}, devices: {len(hardware.devices)}")
        logger.info(f"DATA registers: {len(register_map)}")

        return templates.TemplateResponse(
            "inverters.html",
            {
                "devices": hardware,
                "request": request,
                "data": data,
                "register_map": register_map,
                "modbus_map": modbus_map,
                "page_title": "Inverter/Converter System",
                "device_type": "Inverter2",
                "page": "Inverter",
                "api_endpoint": "inverters",
                "has_ac_in": has_ac_input,
                "error": None
            }
        )
    except Exception as e:
        logger.error(f"Error in Inverters route: {e}")
        return templates.TemplateResponse(
            "inverters.html",
            {
                "hardware": hardware,
                "request": request,
                "register_map": {},
                "error": str(e)
            }
        )

@router.post("/activate-scenario")
async def activate_scenario():
    pass


@router.get("/data")
async def get_inverter_data(deployment: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        hardware = get_inverter(deployment)
        values = hardware.data_acquisition()
        has_ac_in = hardware.has_input_AC(hardware.devices)

        # Update each unit
        for device in hardware.devices:
            unit_id = device['mac']
            if isinstance(values, dict):  # Ensure values is a dictionary
                await bms_store.update_unit_data(unit_id, values[unit_id])
            else:
                logger.error(f"Unexpected values type: {type(values)}")
        data = await bms_store.get_all_data()

        return JSONResponse(content={"data": data, "has_ac_input": has_ac_in, "error": None})
    except Exception as e:
        logger.error(f"Error getting Inverter data: {e}")
        return JSONResponse(content={"data": None, "error": str(e)})


@router.get("/historical/{unit_id}")
async def get_historical_data(unit_id: str, num_points: int = Query(default=800, ge=10, le=20000)):
    try:
        # battery = batteries.get_definition(unit_id)
        logger.info(f"Loading inverter historical data: {unit_id}")
        filename = f"{INVERTER_SYSTEM}_{unit_id}.csv"
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
