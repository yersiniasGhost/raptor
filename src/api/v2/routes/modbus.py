import json
from typing import Annotated
from fastapi import APIRouter, Request, Depends
from . import templates
import logging
from communications.modbus.modbus import modbus_data_acquisition
from bms_store import ModbusMap
from .hardware_deployment import HardwareDeployment, get_hardware


DATA_PATH = "/root/raptor/data"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/modbus", tags=["modbus"])


@router.get("/modbus_register/{data}")
async def read_modbus_register(data: str, hardware_def: Annotated[HardwareDeployment, Depends(get_hardware)]):
    parsed_data = json.loads(data)
    print(parsed_data)
    unit_id = parsed_data['unit_id']
    page = parsed_data['page']

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
    if page == "BMS":
        hardware = hardware_def.batteries.hardware
    elif page == "Inverter":
        hardware = hardware_def.inverter.hardware
    values = modbus_data_acquisition(hardware, m_map, slave_id=unit_id)
    # Handle the modbus read operation here
    return {"success": True, "value": values['ODQ']}
