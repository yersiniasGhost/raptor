from typing import Dict
from asyncio import Lock


# Store for BMS data
class BMSDataStore:
    def __init__(self):
        self.units_data: Dict[str, Dict[str, float]] = {}  # Unit ID -> {register_name: value}
        self.lock = Lock()

    async def add_unit_data(self, unit_id: str, data_values: Dict[str, float]):
        self.units_data[unit_id] = self.units_data[unit_id] | data_values

    async def update_unit_data(self, unit_id: str, register_values: Dict[str, float]):
        if not isinstance(register_values, dict):
            raise ValueError(f"register_values must be a dictionary, got {type(register_values)}")
            
        async with self.lock:
            self.units_data[unit_id] = register_values

    async def get_all_data(self) -> Dict[str, Dict[str, float]]:
        async with self.lock:
            # Return a copy to prevent concurrent modification
            return {k: dict(v) for k, v in self.units_data.items()} 
