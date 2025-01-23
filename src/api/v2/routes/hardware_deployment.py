from fastapi import Request
import logging
from bms_store import ModbusMap
from database.battery_deployment import BatteryDeployment
from communications.electrak.actuator_manager import ActuatorManager


DATA_PATH = "/root/raptor/data"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HardwareDeployment:

    def __init__(self):
        self.batteries = BatteryDeployment.from_json(f"{DATA_PATH}/Esslix/battery_deployment.json")
        self.battery_register_map = ModbusMap.from_json(f"{DATA_PATH}/Esslix/modbus_map.json")

        self.inverter = BatteryDeployment.from_json(f"{DATA_PATH}/Sierra25/converter_deployment.json")
        self.inverter_register_map = ModbusMap.from_json(f"{DATA_PATH}/Sierra25/modbus_map_basic.json")

        self.actuator_manager = ActuatorManager.from_json(f"{DATA_PATH}/ElectrakActuators/electrak_deployment.json")


def get_hardware(request: Request) -> HardwareDeployment:
    return request.app.state.hardware
