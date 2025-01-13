from typing import Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
from pymodbus.client import ModbusSerialClient
from pymodbus.framer import FramerType


@dataclass
class ModbusHardware(ABC):
    framer: FramerType = FramerType.RTU
    baudrate: int = 9600  # Default as specified
    parity: str = 'N'  # No parity as specified
    stopbits: int = 1  # 1 stop-bit as specified
    bytesize: int = 8  # 8 data bits as specified
    timeout: float = 0.2

    MODBUS_SLEEP_BETWEEN_READS: float = 0.05

    def get_modbus_serial_client(self, port: str) -> ModbusSerialClient:
        return ModbusSerialClient(
            port=port,
            framer=self.framer,
            baudrate=self.baudrate,  # Default as specified
            parity=self.parity,  # No parity as specified
            stopbits=self.stopbits,  # 1 stop-bit as specified
            bytesize=self.bytesize,  # 8 data bits as specified
            timeout=self.timeout  # 200ms as specified
        )


    @abstractmethod
    def create_read_message(self, register, slave_id) -> Tuple[bytes, int]:
        """ creates the message that the hardware is expecting """
        pass


