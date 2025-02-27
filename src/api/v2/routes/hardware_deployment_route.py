from typing import Optional
from fastapi import Request
from hardware.hardware_deployment import instantiate_hardware_from_dict
from hardware.electrak.actuator_manager import ActuatorManager
from utils.envvars import EnvVars
from database.database_manager import DatabaseManager
from utils import LogManager
logger = LogManager().get_logger(__name__)


DATA_PATH = "/root/raptor/data"


class HardwareDeploymentRoute:

    def __init__(self):

        db = DatabaseManager(EnvVars().db_path)
        for hardware in db.get_hardware_systems("BMS"):
            self.batteries = instantiate_hardware_from_dict(hardware)
        for hardware in db.get_hardware_systems("Converters"):
            self.inverter = instantiate_hardware_from_dict(hardware)
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
