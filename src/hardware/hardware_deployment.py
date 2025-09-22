import json
from pathlib import Path
from typing import List, Iterator, Dict, Any, Union, Optional, Tuple
from dataclasses import dataclass
from hardware.hardware_base import HardwareBase
from utils import LogManager, EnvVars
from logging import Logger
from hardware.modbus.eve_battery import EveBattery
from hardware.modbus.inview_gateway import InviewGateway
from hardware.mock.mock_hardware import MockHardware
from hardware.adc.ct_hall import CTHall
from hardware.modbus.tristar import Tristar

if EnvVars().enable_simulators:
    from hardware.simulators import BMSSim, PvPanelSimulator, LoadSim


@dataclass
class HardwareDeployment:
    hardware: HardwareBase
    devices: List[Dict[str, Any]]
    scan_groups: Dict[str, Any]
    hardware_id: str
    _definition: Optional[Union[str, dict]] = None
    logger = None

    def __post_init__(self):
        self.logger = LogManager().get_logger("HardwareDeployment")


    def iterate_devices(self) -> Iterator[dict]:
        for device in self.devices:
            yield device


    def read_register(self, register: str) -> dict:
        values = self.hardware.data_acquisition(self.devices, [register], self.hardware_id)
        return values


    def data_acquisition(self, data_type: str = "DATA") -> dict:
        """
        :return: A dictionary of { register_name: value }
        """
        data_registers = self.scan_groups.get(data_type, {}).get('registers', [])
        self.logger.info(f"Acq Data: {data_type}, {len(data_registers)} registers.")
        values = self.hardware.data_acquisition(self.devices, data_registers, self.hardware_id)
        return values

    def get_modbus_maps(self) -> dict:
        data_registers = self.get_points("DATA")
        alarms = self.get_points("ALARM")
        diagnositc = self.get_points("DIAGNOSTIC")
        control = self.get_points("CONTROL")
        all = self.get_points("ALL")
        modbus_map = {"DATA": data_registers, "ALARM": alarms, "DIAGNOSTICS": diagnositc,
                      "CONTROL": control, "ALL": all}
        return modbus_map

    def get_points(self, data_type: str = "DATA") -> Dict[str, Any]:
        if data_type == "ALL":
            return self.hardware.get_points([])
        data_registers = self.scan_groups.get(data_type, {}).get('registers', [])
        points = self.hardware.get_points(data_registers)
        return points

    def ping_hardware(self) -> Tuple[str, Union[str, bool]]:
        return self.hardware.ping_hardware()

    def reset_hardware(self) -> Tuple[str, Union[str, bool]]:
        return self.hardware.reset_hardware()


    def diagnostics(self) -> dict:
        diag_data = self.data_acquisition("DIAGNOSTIC")
        return diag_data

    def alarm_checks(self) -> dict:
        alarm_data = self.data_acquisition("ALARM")
        return alarm_data

    def get_slave_ids(self) -> list:
        return [d['mac'] for d in self.devices]

    def scenario_status(self, mode: str) -> dict:
        return self.hardware.scenario_status(mode, self.devices, self.hardware_id)

    def has_input_AC(self, devices) -> bool:
        return self.hardware.has_input_AC(devices)

    def load_states_config(self) -> Optional[Dict[str, Any]]:
        return self.hardware.load_states_config()

    def get_current_state(self) -> str:
        return self.hardware.get_current_state()

    def get_available_states(self):
        return self.hardware.get_available_states()

    def set_operational_state(self, state_name: str, parameter_overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        return self.hardware.set_operational_state(state_name, parameter_overrides)


    def get_identifiers(self):
        try:
            ids = self.hardware.get_identifier(self.devices)
            for mac, local_id in ids.items():
                for d in self.devices:
                    if d['mac'] == mac:
                        d['identifier'] = local_id
        except Exception as e:
            self.logger.error(f"Could not get identifiers {self.hardware_id}, {e}", exc_info=True)


    @property
    def definition(self):
        return self._definition

    @definition.setter
    def definition(self, value):
        self._definition = value


def instantiate_hardware_from_dict(hardware: Dict[str, Any], logger: Logger,
                                   keep_definition: bool = True) -> HardwareDeployment:
    class_path = hardware.get("driver_path")
    if not class_path:
        raise ValueError(f"Invalid configuration data.  Missing hardware type")

    # Split the class path into module path and class name
    try:
        module_path, class_name = class_path.rsplit('.', 1)
    except ValueError:
        raise ValueError(f"Invalid class path format: {class_path}. Expected format: 'module.path.ClassName'")

    try:
        cls = globals().get(class_name, None)
        if not cls:
            logger.error(f"Cannot find class name: {class_name}")
            raise ValueError(f"Cannot find class name: {class_name}")
        logger.info(f"Instantiating {class_name} With: {hardware.get('parameters')}")
        constructor_config = hardware.get("parameters", {})
        constructor_config['states_config_path'] = "/root/raptor/data/Sierra25/sierra25_states.json"
        hardware_instance = cls(**constructor_config)
        deployment = HardwareDeployment(hardware=hardware_instance,
                                        devices=hardware.get('devices'),
                                        scan_groups=hardware.get('scan_groups', {}),
                                        hardware_id=hardware.get('external_ref')
                                        )
        if keep_definition:
            deployment.definition = hardware
        return deployment

    except ImportError:
        logger.error(f"Cannot instantiate class: {class_name}", exc_info=True)
        raise ImportError(f"Could not import module: {module_path}")
    except AttributeError:
        logger.error(f"Cannot instantiate class: {class_name}", exc_info=True)
        raise ImportError(f"Could not find class {class_name} in module {module_path}")


def load_hardware_from_json_file(json_file: Union[Path, str],
                                 keep_definition: bool = False) -> HardwareDeployment:
    json_path = Path(json_file)
    if not json_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {json_file}")

    with json_path.open('r') as f:
        try:
            data = json.load(f)
            return instantiate_hardware_from_dict(data)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in configuration file: {json_file}")
