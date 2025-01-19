# routes/bms.py
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse
from . import templates
import logging
from communications.modbus.test_map import read_holding_registers
from bms_store import BMSDataStore, ModbusMap
from database.battery_deployment import BatteryDeployment

DATA_PATH = "/root/raptor/data"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bms", tags=["bms"])

# Load register map
try:
    # Initialize BMS data store
    bms_store = BMSDataStore()
    update_task = None
    batteries = BatteryDeployment.from_json(f"{DATA_PATH}/Esslix/battery_deployment.json")
    register_map = ModbusMap.from_json(f"{DATA_PATH}/Esslix/modbus_map.json")
except Exception as e:
    logger.error(f"Failed to load Battery configuration files: {e}")
    register_map = None


@router.get("/data")
async def get_bms_data():
    try:
        # Update each unit
        for unit_id in batteries.iterate_slave_ids():
            # Assuming read_holding_registers returns a Dict[str, float]
            values = read_holding_registers(register_map, slave_id=unit_id)
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
async def get_historical_data(unit_id: int):
    try:
        # battery = batteries.get_definition(unit_id)
        filename = f"modbus_slave_{unit_id}.csv"

        # Use Python's file handling
        with open(filename, 'r') as file:
            content = file.read()

        return JSONResponse(content={"data": content, "error": None})
    except FileNotFoundError:
        logger.error(f"CSV file not found for unit {unit_id}")
        return JSONResponse(content={"data": None, "error": f"No historical data found for unit {unit_id}"})
    except Exception as e:
        logger.error(f"Error reading historical data for unit {unit_id}: {e}")
        return JSONResponse(content={"data": None, "error": str(e)})


@router.get("/")
async def bms(request: Request):
    try:
        bms_data = await bms_store.get_all_data()
        return templates.TemplateResponse(
            "bms_v.html",
            {
                "batteries": batteries,
                "request": request,
                "bms_data": bms_data,
                "register_map": register_map,
                "error": None
            }
        )
    except Exception as e:
        logger.error(f"Error in BMS route: {e}")
        return templates.TemplateResponse(
            "bms.html",
            {
                "batteries": [],
                "request": request,
                "bms_data": {},
                "register_map": register_map,
                "error": str(e)
            }
        )
