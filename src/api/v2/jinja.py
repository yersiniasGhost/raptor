from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import asyncio
import uvicorn
from typing import Dict
from communications.electrak.actuator_manager import ActuatorManager
from communications.gpio_controller.banner_alarm import BannerAlarm, BannerAlarmException
from communications.modbus.test_map import read_holding_registers
from bms_store import BMSDataStore, ModbusMap

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize BMS data store
bms_store = BMSDataStore()
update_task = None



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown

# Initialize app with lifespan handler
app = FastAPI(title="Multi-Actuator Control System", lifespan=lifespan)

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Load register map
try:
    register_map = ModbusMap.from_json("modbus_map.json")
except Exception as e:
    logger.error(f"Failed to load modbus_map.json: {e}")
    register_map = None


@app.get("/bms/data")
async def get_bms_data():
    try:
        # Update each unit
        units = [1, 2, 3]  # Replace with your actual unit IDs
        for unit_id in units:
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

@app.get("/bms/historical/{unit_id}")
async def get_historical_data(unit_id: int):
    try:
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


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request}
    )

@app.get("/bms")
async def bms(request: Request):
    try:
        bms_data = await bms_store.get_all_data()
        return templates.TemplateResponse(
            "bms.html",
            {
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
                "request": request,
                "bms_data": {},
                "register_map": register_map,
                "error": str(e)
            }
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
