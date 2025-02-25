from typing import Optional
from fastapi import Request
from hardware.hardware_deployment import load_hardware_from_json_file
from hardware.electrak.actuator_manager import ActuatorManager
from utils import LogManager
logger = LogManager().get_logger(__name__)


DATA_PATH = "/root/raptor/data"


class HardwareDeploymentRoute:

    def __init__(self):

        self.batteries = load_hardware_from_json_file(f"{DATA_PATH}/Esslix/battery_deployment.json",
                                                      keep_definition=True)
        self.inverter = load_hardware_from_json_file(f"{DATA_PATH}/Sierra25/converter_deployment.json",
                                                     keep_definition=True)
        self.actuator_manager = ActuatorManager.from_json(f"{DATA_PATH}/ElectrakActuators/electrak_deployment.json")

    def get_hardware_definition(self, hardware_type: str) -> Optional[dict]:
        if hardware_type == "BMS":
            return self.batteries.definition
        if hardware_type == "Inverter":
            return self.inverter.definition
        if hardware_type == "Actuators":
            return self.actuator_manager.hardware_definition
        else:
            return None


def get_hardware(request: Request) -> HardwareDeploymentRoute:
    return request.app.state.hardware
