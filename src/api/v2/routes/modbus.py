import json
from typing import Annotated
from fastapi import APIRouter, Depends
import logging
from hardware.modbus.modbus import modbus_data_acquisition, modbus_data_write
from .hardware_deployment import HardwareDeployment, get_hardware
from hardware.modbus.modbus_map import ModbusMap


DATA_PATH = "/root/raptor/data"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/modbus", tags=["modbus"])


@router.get("/modbus_write/{data}")
async def write_modbus_register(data: str, hardware_def: Annotated[HardwareDeployment, Depends(get_hardware)]):
    parsed_data = json.loads(data)
    print(parsed_data)
    unit_id = parsed_data['unit_id']
    page = parsed_data['page']
    m_map = ModbusMap.from_dict({"registers": [
        {
            "name": "ODW",
            "data_type": parsed_data['type'],
            "address": parsed_data['register'],
            "units": "",
            "conversion_factor": 1.0,
            "description": "On demand write",
            "read_write": "RW"
        }
    ]})
    if page == "BMS":
        hardware = hardware_def.batteries.hardware
    elif page == "Inverter":
        hardware = hardware_def.inverter.hardware
    values = modbus_data_write(hardware, m_map, slave_id=unit_id,
                               register_name="ODW", value=parsed_data['value'])
    # Handle the modbus read operation here
    return {"success": True, "value":values }


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
    print(values)
    # Handle the modbus read operation here
    return {"success": True, "value": values['ODQ']}
