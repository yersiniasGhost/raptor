# models.py
from dataclasses import dataclass
from typing import List, Optional, Dict
import json
from asyncio import Lock
from hardware.modbus.modbus_map import ModbusMap, ModbusRegister


# Store for BMS data
class BMSDataStore:
    def __init__(self):
        self.units_data: Dict[int, Dict[str, float]] = {}  # Unit ID -> {register_name: value}
        self.lock = Lock()


    async def update_unit_data(self, unit_id: int, register_values: Dict[str, float]):
        if not isinstance(register_values, dict):
            raise ValueError(f"register_values must be a dictionary, got {type(register_values)}")
            
        async with self.lock:
            self.units_data[unit_id] = register_values

    async def get_all_data(self) -> Dict[str, Dict[str, float]]:
        async with self.lock:
            # Return a copy to prevent concurrent modification
            return {k: dict(v) for k, v in self.units_data.items()} 
