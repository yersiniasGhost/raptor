from typing import List, Iterator, Dict
from dataclasses import dataclass, field
import json


@dataclass
class BatteryDefinition:
    mac: str
    slave_id: int


@dataclass
class BatteryDeployment:
    batteries: List[BatteryDefinition]
    battery_look_up: Dict[int, BatteryDefinition] = field(default_factory=dict)

    def __post_init__(self):
        for bat in self.batteries:
            self.battery_look_up[bat.slave_id] = bat

    @classmethod
    def from_json(cls, json_file: str) -> 'BatteryDeployment':
        with open(json_file, 'r') as f:
            data = json.load(f)
            return cls.from_dict(data)

    @classmethod
    def from_dict(cls, battery_map: List[dict]) -> 'BatteryDeployment':
        batteries = [BatteryDefinition(**bat) for bat in battery_map]
        return cls(batteries=batteries)

    def get_slave_ids(self) -> List[int]:
        return [bat.slave_id for bat in self.batteries]

    def iterate_slave_ids(self) -> Iterator[int]:
        for bat in self.batteries:
            yield bat.slave_id

    def each_battery(self) -> Iterator[BatteryDefinition]:
        for bat in self.batteries:
            yield bat

