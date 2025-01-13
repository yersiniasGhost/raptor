from typing import Tuple
from abc import ABC, abstractmethod
from pymodbus.client import ModbusSerialClient


class ModbusHardware(ABC):

    MODBUS_SLEEP_BETWEEN_READS = 0.05

    @abstractmethod
    def get_modbus_serial_client(self, port: str) -> ModbusSerialClient:
        """ Instantiate the hardware specific client """
        pass

    @abstractmethod
    def create_read_message(self, register, slave_id) -> Tuple[bytes, int]:
        """ creates the message that the hardware is expecting """
        pass


