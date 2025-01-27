# routes/bms.py
import csv
from typing import Annotated
from collections import deque
import json
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from . import templates
import logging
from communications.modbus.modbus import modbus_data_acquisition
from bms_store import BMSDataStore, ModbusMap
from .hardware_deployment import HardwareDeployment, get_hardware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bms", tags=["bms"])

bms_store = BMSDataStore()


def get_batteries(deployment: HardwareDeployment):
    return deployment.batteries, deployment.battery_register_map


@router.get("/data")
async def get_bms_data(hardware: Annotated[HardwareDeployment, Depends(get_hardware)]):
    try:
        # Update each unit
        batteries, register_map = get_batteries(hardware)
        for unit_id in batteries.iterate_slave_ids():
            # Assuming read_holding_registers returns a Dict[str, float]
            values = modbus_data_acquisition(batteries.hardware, register_map, slave_id=unit_id)
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
        filename = f"battery_{unit_id}.csv"
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


@router.get("/modbus_register/{data}")
async def read_modbus_register(data: str, hardware: Annotated[HardwareDeployment, Depends(get_hardware)]):
    parsed_data = json.loads(data)
    unit_id = parsed_data['unit_id']
    m_map = ModbusMap.from_dict({"registers": [
        {
            "name": "ODQ",
            "data_type": parsed_data['type'],
            "address": parsed_data['register'],
            "units": "",
            "conversion_factor": 1.0,
            "description": "On demand query"
        }
    ]})
    batteries, _ = get_batteries(hardware)
    values = modbus_data_acquisition(batteries.hardware, m_map, slave_id=unit_id)
    # Handle the modbus read operation here
    return {"success": True, "value": values['ODQ']}


@router.get("/")
async def bms(request: Request, hardware: Annotated[HardwareDeployment, Depends(get_hardware)]):
    batteries, register_map = get_batteries(hardware)
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
            "bms_v.html",
            {
                "batteries": [],
                "request": request,
                "bms_data": {},
                "register_map": register_map,
                "error": str(e)
            }
        )
