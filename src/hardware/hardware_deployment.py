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
from hardware.adc.ct_hall import ADCHardware
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

    def data_acquisition(self, data_type: str = "DATA") -> dict:
        """
        :return: A dictionary of { register_name: value }
        """
        data_registers = self.scan_groups.get(data_type, {}).get('registers', [])
        self.logger.info(f"Acq Data: {data_type}, {len(data_registers)} registers.")
        values = self.hardware.data_acquisition(self.devices, data_registers, self.hardware_id)
        return values

    def get_points(self, data_type: str = "DATA") -> List[dict]:
        data_registers = self.scan_groups.get(data_type, {}).get('registers', [])
        points = self.hardware.get_points(data_registers)
        return points

    def ping_hardware(self) -> Tuple[str, Union[str, bool]]:
        return "Ping TBD", True

    def diagnostics(self) -> dict:
        diag_data = self.data_acquisition("DIAGNOSTIC")
        return diag_data

    def alarm_checks(self) -> dict:
        alarm_data = self.data_acquisition("ALARM")
        return alarm_data

    def get_slave_ids(self) -> list:
        return [d['mac'] for d in self.devices]

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
        # Import the module and get the class
        # module = importlib.import_module(module_path)
        # cls = getattr(module, class_name)
        cls = globals()[class_name]
        logger.info(f"Instantiating {class_name}")
        constructor_config = hardware.get("parameters", {})
        hardware_instance = cls(**constructor_config)
        deployment = HardwareDeployment(hardware=hardware_instance,
                                        devices=hardware.get('devices'),
                                        scan_groups=hardware.get('scan_groups', {}),
                                        hardware_id=hardware.get('external_ref')
                                        )
        if keep_definition:
            logger.info(f"Keeping definition: {hardware}")
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
