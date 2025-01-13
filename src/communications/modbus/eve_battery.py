from typing import Tuple, Optional
from dataclasses import dataclass
from pymodbus.client import ModbusSerialClient
from pymodbus.framer import FramerType
from modbus_hardware import ModbusHardware
from modbus_map import ModbusRegister


@dataclass
class EveBattery(ModbusHardware):

    framer: FramerType = FramerType.RTU
    baudrate: int = 9600  # Default as specified
    parity: str = 'N'  # No parity as specified
    stopbits: int = 1  # 1 stop-bit as specified
    bytesize: int = 8  # 8 data bits as specified
    timeout: float = 0.2

    def get_modbus_serial_client(self, port: str) -> ModbusSerialClient:
        return ModbusSerialClient(
            port=port,
            framer=FramerType.RTU,
            baudrate=self.baudrate,  # Default as specified
            parity=self.parity,  # No parity as specified
            stopbits=self.stopbits,  # 1 stop-bit as specified
            bytesize=self.bytesize,  # 8 data bits as specified
            timeout=self.timeout  # 200ms as specified
        )

    # Return the message and the CRC value if required.
    def create_read_message(self, register: ModbusRegister, slave_id: int) -> Tuple[bytes, Optional[int]]:
        address = register.get_addresses()[0]
        message = bytes([
            slave_id,  # Slave Address (0x01-0x10)
            0x03,  # Function Code (Read Registers)
            address >> 8,  # Starting Address (Hi)
            address & 0xFF,  # Starting Address (Lo)
            0x00,  # Number of Registers (Hi)
            0x01  # Number of Registers (Lo)
        ])
        return message, None

