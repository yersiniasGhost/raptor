import json
from typing import Annotated
from fastapi import APIRouter, Depends

from hardware.modbus.modbus_hardware import modbus_data_write, modbus_data_read
from hardware.modbus.modbus_hardware import modbus_data_acquisition
from .hardware_deployment_route import HardwareDeploymentRoute, get_hardware
from hardware.modbus.modbus_map import ModbusMap, ModbusRegisterType
from utils import LogManager


DATA_PATH = "/root/raptor/data"

logger = LogManager().get_logger(__name__)
router = APIRouter(prefix="/modbus", tags=["modbus"])


@router.post("/modbus_write/{data}")
async def write_modbus_register(data: str, hardware_def: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    parsed_data = json.loads(data)
    unit_id = parsed_data['unit_id']
    page = parsed_data['page']
    register_key = parsed_data['register_key']
    m_map = ModbusMap.from_dict({"ODW": {
        "name": "ODW",
        "data_type": parsed_data['data_type'],
        "address": parsed_data['register'],
        "units": "",
        "conversion_factor": 1.0,
        "description": "On demand write",
        "access": "RW"
    }})
    if page == "BMS":
        hardware = hardware_def.batteries.hardware
    elif page == "Inverter":
        hardware = hardware_def.inverter.hardware
    elif page == "Charge Controller":
        hardware = hardware_def.charge_controller.hardware
    else:
        logger.error(f"Invalid page: {page}")
        return {"success": False, "error": f"Invalid page: {page}"}
    try:
        write_success = modbus_data_write(hardware, slave_id=unit_id,
                                          register_name=register_key, value=parsed_data['value'])
    except Exception as e:
        logger.error(e)
        return {"success": False, "error": str(e)}

    if not write_success:
        return {"success": False, "error": "Write operation failed"}

    # Read back the written value for confirmation
    values = modbus_data_read(hardware, register_key, slave_id=unit_id)
    return {"success": True, "value": values.get("ODW", parsed_data['value'])}


@router.get("/modbus_register/{data}")
async def read_modbus_register(data: str, hardware_def: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    parsed_data = json.loads(data)
    logger.info(f"Reading from MODBUS: {parsed_data}")
    unit_id = parsed_data['unit_id']
    page = parsed_data['page']

    if page == "BMS":
        hardware = hardware_def.batteries.hardware
    elif page == "Inverter":
        hardware = hardware_def.inverter.hardware
    elif page == "Charge Controller":
        hardware = hardware_def.charge_controller.hardware
    else:
        logger.error(F"Invalid page : {page}")
        return {"success": False, "error": F"Invalid page: {page}"}
    register_key = parsed_data['register_key']
    values = modbus_data_acquisition(hardware, hardware.modbus_map.get_registers_by_key([register_key]), slave_id=unit_id)
    logger.info(values)
    return {"success": True, "value": values[register_key]}


@router.get("/modbus_register_data/{data}")
async def read_modbus_register_by_name(data: str, hardware_def: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    parsed_data = json.loads(data)
    logger.info(f"Reading from MODBUS: {parsed_data}")
    unit_id = parsed_data['unit_id']
    page = parsed_data['page']

    if page == "BMS":
        hardware = hardware_def.batteries.hardware
    elif page == "Inverter":
        hardware = hardware_def.inverter.hardware
    elif page == "Charge Controller":
        hardware = hardware_def.charge_controller.hardware
    else:
        return {"success": False, "error": f"Invalid page: {page}"}
    print(parsed_data)
    reg_name = parsed_data['register_key']

    values = modbus_data_acquisition(hardware, hardware.modbus_map.get_registers_by_key([reg_name]), slave_id=unit_id)
    if reg_name not in values:
        logger.error(f"Didn't get values back from modbus: {values}")
        return {"success": False, "error": f"Couldn't read {reg_name}"}

    return {"success": True, "value": values[reg_name]}
