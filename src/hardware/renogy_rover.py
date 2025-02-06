from typing import Tuple, Optional, Dict
from communications.modbus.modbus_hardware import ModbusHardware, ModbusClientType
from communications.modbus.modbus_map import ModbusRegister, ModbusDatatype


class RenogyRover(ModbusHardware):
    def __post_init__(self):
        print("Evebattery post")
        self.client_type = ModbusClientType.RTU


ERROR_CODES = {
    0: 'None',
    1: 'reserved',
    2: 'reserved',
    3: 'reserved',
    4: 'reserved',
    5: 'reserved',
    6: 'reserved',
    7: 'reserved',
    8: 'reserved',
    9: 'reserved',
    10: 'reserved',
    11: 'reserved',
    12: 'reserved',
    13: 'reserved',
    14: 'reserved',
    15: 'reserved',
    16: 'battery over-discharge',
    17: 'battery over-voltage',
    18: 'battery under-voltage warning',
    19: 'load short circuit',
    20: 'load overpower or load over-current',
    21: 'controller temperature too high',
    22: 'ambient temperature too high',
    23: 'photovoltaic input overpower',
    24: 'photovoltaic input side short circuit',
    25: 'photovoltaic input side over- voltage',
    26: 'solar panel counter-current',
    27: 'solar panel working point over-voltage',
    28: 'solar panel reversely connected',
    29: 'anti-reverse MOS short',
    30: 'circuit, charge MOS short',
    31: 'reserved',
}
