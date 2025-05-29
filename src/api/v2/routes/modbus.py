import json
from typing import Annotated
from fastapi import APIRouter, Depends

from hardware.modbus.modbus import modbus_data_write
from hardware.modbus.modbus_hardware import modbus_data_acquisition
from .hardware_deployment_route import HardwareDeploymentRoute, get_hardware
from hardware.modbus.modbus_map import ModbusMap
from utils import LogManager


DATA_PATH = "/root/raptor/data"

logger = LogManager().get_logger(__name__)
router = APIRouter(prefix="/modbus", tags=["modbus"])


@router.get("/modbus_write/{data}")
async def write_modbus_register(data: str, hardware_def: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    parsed_data = json.loads(data)
    unit_id = parsed_data['unit_id']
    page = parsed_data['page']
    m_map = ModbusMap.from_dict({"registers": {"ODW":
        {
            "name": "ODW",
            "data_type": parsed_data['type'],
            "address": parsed_data['register'],
            "units": "",
            "conversion_factor": 1.0,
            "description": "On demand write",
            "read_write": "RW"
        }
    }})
    if page == "BMS":
        hardware = hardware_def.batteries.hardware
    elif page == "Inverter":
        hardware = hardware_def.inverter.hardware
    values = modbus_data_write(hardware, m_map, slave_id=unit_id,
                               register_name="ODW", value=parsed_data['value'])
    # Handle the modbus read operation here
    return {"success": True, "value": values}


@router.get("/modbus_register/{data}")
async def read_modbus_register(data: str, hardware_def: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    parsed_data = json.loads(data)
    logger.info(f"Reading from MODBUS: {parsed_data}")
    unit_id = parsed_data['unit_id']
    page = parsed_data['page']
    range = parsed_data['range']

    m_map = ModbusMap.from_dict({"ODQ": {
            "name": "ODQ",
            "data_type": parsed_data['data_type'],
            "address": parsed_data['register'],
            "range_size": range,
            "type": parsed_data['register_type'],
            "slave_id": int(parsed_data['unit_id']),
            "units": "",
            "conversion_factor": 1.0,
            "description": "On demand query"
        }
    })
    if page == "BMS":
        hardware = hardware_def.batteries.hardware
    elif page == "Inverter":
        hardware = hardware_def.inverter.hardware
    elif page == "Charge Controller":
        hardware = hardware_def.charge_controller.hardware
    values = modbus_data_acquisition(hardware, m_map.get_registers(["ODQ"]), slave_id=unit_id)
    logger.info(values)
    return {"success": True, "value": values['ODQ']}
