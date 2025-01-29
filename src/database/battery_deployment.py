from typing import List, Iterator, Dict, Optional
from dataclasses import dataclass, field
import json
from communications.modbus.modbus_hardware import ModbusHardware
from database.hardware import load_hardware_from_dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class BatteryDefinition:
    mac: str
    slave_id: int


@dataclass
class BatteryDeployment:
    hardware_definition: Dict[str, str]
    batteries: List[BatteryDefinition]
    battery_look_up: Dict[int, BatteryDefinition] = field(default_factory=dict)
    hardware: Optional[ModbusHardware] = None


    def __post_init__(self):
        for bat in self.batteries:
            self.battery_look_up[bat.slave_id] = bat
        self.hardware = load_hardware_from_dict(self.hardware_definition)

    @classmethod
    def from_json(cls, json_file: str) -> 'BatteryDeployment':
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"Failed to read file {json_file}: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_file}: {str(e)}")
            raise
        logger.debug(f"Loaded JSON file:{json_file} \nDATA\n{data}")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, battery_map: dict) -> 'BatteryDeployment':
        try:
            hardware = battery_map['hardware']
            battery_configs = battery_map['devices']
        except KeyError as e:
            logger.error(f"Missing required configuration field: {e}")
            raise
        try:
            batteries = [BatteryDefinition(**config) for config in battery_configs]
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid battery configuration: {e}")
            raise ValueError(f"Failed to create battery definition: {e}")
        return cls(hardware_definition=battery_map, batteries=batteries)


    def get_slave_ids(self) -> List[int]:
        return [bat.slave_id for bat in self.batteries]

    def iterate_slave_ids(self) -> Iterator[int]:
        for bat in self.batteries:
            yield bat.slave_id

    def each_unit(self) -> Iterator[BatteryDefinition]:
        for bat in self.batteries:
            yield bat

