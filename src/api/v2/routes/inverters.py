from typing import Annotated
from collections import deque
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from . import templates
import logging
from bms_store import BMSDataStore
from .hardware_deployment import HardwareDeployment, get_hardware
from communications.modbus.modbus import modbus_data_acquisition

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inverters", tags=["inverters"])
BASE_DIR = Path(__file__).resolve().parent

# Load register map
try:
    # Initialize BMS data store
    bms_store = BMSDataStore()
    update_task = None
except Exception as e:
    logger.error(f"Failed to load Inverter configuration files: {e}")


def get_inverter(deployment: HardwareDeployment):
    return deployment.inverter, deployment.inverter_register_map


@router.get("/")
async def inverters(request: Request, deployment: Annotated[HardwareDeployment, Depends(get_hardware)]):
    try:
        data = await bms_store.get_all_data()
        hardware, register_map = get_inverter(deployment)
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
async def get_bms_data(deployment: Annotated[HardwareDeployment, Depends(get_hardware)]):
    try:
        hardware, register_map = get_inverter(deployment)
        # Update each unit
        for unit_id in hardware.iterate_slave_ids():
            # Assuming read_holding_registers returns a Dict[str, float]
            values = modbus_data_acquisition(hardware.hardware, register_map, slave_id=unit_id)
            if isinstance(values, dict):  # Ensure values is a dictionary
                await bms_store.update_unit_data(unit_id, values)
            else:
                logger.error(f"Unexpected values type: {type(values)}")
        data = await bms_store.get_all_data()
        print(data)
        print('-----')
        return JSONResponse(content={"data": data, "error": None})
    except Exception as e:
        logger.error(f"Error getting BMS data: {e}")
        return JSONResponse(content={"data": None, "error": str(e)})


@router.get("/historical/{unit_id}")
async def get_historical_data(unit_id: int, num_points: int = Query(default=4000, ge=100, le=10000)):
    try:
        # battery = batteries.get_definition(unit_id)
        filename = f"{BASE_DIR}/inverter_{unit_id}.csv"
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
