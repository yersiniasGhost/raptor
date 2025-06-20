import json
from typing import Annotated
from fastapi import APIRouter, Request, Form

from hardware.modbus.modbus import modbus_data_write
from hardware.modbus.modbus_hardware import modbus_data_acquisition
from .hardware_deployment_route import HardwareDeploymentRoute, get_hardware
from hardware.modbus.modbus_map import ModbusMap
from utils import LogManager


DATA_PATH = "/root/raptor/data"

logger = LogManager().get_logger(__name__)
router = APIRouter(prefix="/history_data", tags=["history_data"])


@router.post("/")
async def handle_history_action(request: Request, system: str = Form(...), action: str = Form(...)):
    if action == "clear":
        filename = f"{system}_{unit_id}.csv"

