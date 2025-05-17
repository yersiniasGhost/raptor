from typing import Optional, Union
from fastapi import Request
from hardware.hardware_deployment import instantiate_hardware_from_dict, HardwareDeployment
from hardware.electrak.actuator_manager import ActuatorManager
from utils.envvars import EnvVars
from database.database_manager import DatabaseManager
from utils import LogManager


DATA_PATH = "/root/raptor/data"


class HardwareDeploymentRoute:

    def __init__(self):
        self.logger = LogManager().get_logger("HardwareDepRoute")
        self.inverter = None
        self.batteries = None
        self.actuator_manager = None
        self.charge_controller = None

        db = DatabaseManager(EnvVars().db_path)
        for hardware in db.get_hardware_systems("Actuators"):
            self.logger.info(f"Adding Actuators")
            self.logger.info(f"TOD: {hardware}")
            try:
                self.actuator_manager = ActuatorManager.from_dict(hardware, self.logger)
            except Exception as e:
                self.logger.error(f"Failed to load ActuatorManager, {e}")
                self.actuator_manager = None

        for hardware in db.get_hardware_systems("BMS"):
            self.logger.info(f"Adding BMS system")
            self.logger.info(f"TOD: {hardware}")
            self.batteries = instantiate_hardware_from_dict(hardware, self.logger, True)
            self.batteries.get_identifiers()
        for hardware in db.get_hardware_systems("Converters"):
            self.logger.info(f"Adding Converter/Inverter system")
            self.logger.info(f"TOD: {hardware}")
            self.inverter = instantiate_hardware_from_dict(hardware, self.logger, True)

        for hardware in db.get_hardware_systems("PV"):
            self.logger.info(f"Adding PV systems")
            self.logger.info(f"TOD: {hardware}")
            self.pv_cts = instantiate_hardware_from_dict(hardware, self.logger, True)

        for hardware in db.get_hardware_systems("Charge Controller"):
            self.logger.info(f"Adding Charge Controller systems")
            self.logger.info(f"TOD: {hardware}")
            self.charge_controller = instantiate_hardware_from_dict(hardware, self.logger, True)



    def get_hardware(self, hardware_type: str) -> Union[ActuatorManager, HardwareDeployment]:
        if hardware_type == "BMS":
            return self.batteries
        if hardware_type == "Inverter":
            return self.inverter
        if hardware_type == "Actuators":
            return self.actuator_manager
        return None


    def get_hardware_definition(self, hardware_type: str) -> Optional[dict]:
        if hardware_type == "BMS":
            if self.batteries:
                return self.batteries.definition
            return {"message": "NO Battery BMS assigned."}
        if hardware_type == "Inverter":
            if self.inverter:
                return self.inverter.definition
            return {"message": "NO INVERTER/CONVERTER assigned."}
        if hardware_type == "Actuators":
            if self.actuator_manager:
                return self.actuator_manager.hardware_definition
            return {"message": "NO Actuators installed (check config)"}
        if hardware_type == "Charge Controller":
            if self.charge_controller:
                return self.charge_controller.definition
            return {"message": "No Charge Controller assigned"}
        else:
            return {"message": f"{hardware_type} not yet supported."}


def get_hardware(request: Request) -> HardwareDeploymentRoute:
    return request.app.state.hardware
