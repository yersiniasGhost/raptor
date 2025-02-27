import importlib
import inspect
from typing import Union
from pathlib import Path
import json

from hardware.modbus.modbus_hardware import ModbusHardware
from hardware.modbus import InviewGateway
from hardware.modbus import EveBattery
from hardware.renogy_rover import RenogyRover


# TODO:  Add the load/save of hardware to the SQLite local database.

def load_hardware_from_dict(hardware_config: dict) -> ModbusHardware:
    hardware = hardware_config.get('hardware')
    class_path = hardware.get("type")

    if not class_path:
        raise ValueError(f"Invalid configuration data.  Missing hardware type")

    # Split the class path into module path and class name
    try:
        module_path, class_name = class_path.rsplit('.', 1)
    except ValueError:
        raise ValueError(f"Invalid class path format: {class_path}. Expected format: 'module.path.ClassName'")

    try:
        # Import the module and get the class
        cls = globals()[class_name]

        # Verify it's a subclass of ModbusHardware
        if not inspect.isclass(cls) or not issubclass(cls, ModbusHardware):
            raise ValueError(f"Class {class_name} is not a subclass of ModbusHardware")

        constructor_config = hardware.get("parameters", {})
        return cls(**constructor_config)

    except ImportError:
        raise ImportError(f"Could not import module: {module_path}")
    except AttributeError:
        raise ImportError(f"Could not find class {class_name} in module {module_path}")


def load_hardware_from_json_file(json_file: Union[Path, str]) -> ModbusHardware:
    json_path = Path(json_file)
    if not json_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {json_file}")

    with json_path.open('r') as f:
        try:
            data = json.load(f)
            return load_hardware_from_dict(data)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in configuration file: {json_file}")
