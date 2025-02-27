import json
from pathlib import Path
from typing import List, Iterator, Dict, Any, Union, Optional
from dataclasses import dataclass
from hardware.hardware_base import HardwareBase
from hardware.modbus.eve_battery import EveBattery
from hardware.modbus.inview_gateway import InviewGateway


@dataclass
class HardwareDeployment:
    hardware: HardwareBase
    devices: List[Dict[str, Any]]
    scan_groups: Dict[str, Any]
    hardware_id: str
    _definition: Optional[Union[str, dict]] = None


    def iterate_devices(self) -> Iterator[dict]:
        for device in self.devices:
            yield device

    def data_acquisition(self, format: str) -> dict:
        """
        :return: A dictionary of { register_name: value }
        """
        data_registers = self.scan_groups.get("DATA", {}).get('registers', [])
        values = self.hardware.data_acquisition(self.devices, data_registers)
        return values

    def alarm_checks(self) -> dict:
        """ Perform a check on the alarms associated with this hardware device """
        pass

    @property
    def definition(self):
        return self._definition

    @definition.setter
    def definition(self, value):
        self._definition = value


def instantiate_hardware_from_dict(hardware: Dict[str, Any],
                                   keep_definition: bool = False) -> HardwareDeployment:
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
        constructor_config = hardware.get("parameters", {})
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
        raise ImportError(f"Could not import module: {module_path}")
    except AttributeError:
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
