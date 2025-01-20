from typing import List, Iterator, Dict, Optional
from dataclasses import dataclass, field
import json
from communications.modbus.modbus_hardware import ModbusHardware
from communications.modbus.eve_battery import EveBattery
import logging

logger = logging.getLogger(__name__)

@dataclass
class BatteryDefinition:
    mac: str
    slave_id: int


@dataclass
class BatteryDeployment:
    hardware: Dict[str, str]
    batteries: List[BatteryDefinition]
    battery_look_up: Dict[int, BatteryDefinition] = field(default_factory=dict)
    battery_hardware: Optional[ModbusHardware] = None


    def __post_init__(self):
        for bat in self.batteries:
            self.battery_look_up[bat.slave_id] = bat
        if self.hardware["type"] == "EsslixV1":
            self.battery_hardware = EveBattery(port=self.hardware['port'])
            print(self.battery_hardware)

    @classmethod
    def from_json(cls, json_file: str) -> 'BatteryDeployment':
        with open(json_file, 'r') as f:
            data = json.load(f)
            logger.info(f"Loaded battery deployment configuration JSON: {data}")
            return cls.from_dict(data)

    @classmethod
    def from_dict(cls, battery_map: dict) -> 'BatteryDeployment':
        batteries = [BatteryDefinition(**bat) for bat in battery_map['batteries']]
        hardware = battery_map['hardware']
        return cls(batteries=batteries, hardware=hardware)

    def get_slave_ids(self) -> List[int]:
        return [bat.slave_id for bat in self.batteries]

    def iterate_slave_ids(self) -> Iterator[int]:
        for bat in self.batteries:
            yield bat.slave_id

    def each_battery(self) -> Iterator[BatteryDefinition]:
        for bat in self.batteries:
            yield bat

