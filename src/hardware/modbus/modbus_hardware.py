from typing import Tuple, Union, Optional
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod
from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.framer import FramerType


class ModbusClientType(Enum):
    TCP=1,
    RTU=2,
    NA=3


@dataclass
class ModbusHardware(ABC):
    framer: FramerType = FramerType.RTU
    baudrate: int = 9600  # Default as specified
    parity: str = 'N'  # No parity as specified
    stopbits: int = 1  # 1 stop-bit as specified
    bytesize: int = 8  # 8 data bits as specified
    timeout: float = 0.2
    client_type: ModbusClientType = ModbusClientType.RTU
    host: str = ""
    port: Optional[Union[str, int]] = None

    MODBUS_SLEEP_BETWEEN_READS: float = 0.05

    def get_modbus_serial_client(self) -> ModbusSerialClient:
        return ModbusSerialClient(
            port=self.port,
            framer=self.framer,
            baudrate=self.baudrate,  # Default as specified
            parity=self.parity,  # No parity as specified
            stopbits=self.stopbits,  # 1 stop-bit as specified
            bytesize=self.bytesize,  # 8 data bits as specified
            timeout=self.timeout  # 200ms as specified
        )

    def get_modbus_tcp_client(self) -> ModbusTcpClient:
        # TODO Error checking required or rely on library?
        return ModbusTcpClient(host=self.host, port=int(self.port)) #, source_address=('10.250.250.2', 0))


    def get_modbus_client(self) -> Union[ModbusTcpClient, ModbusSerialClient]:
        if self.client_type == ModbusClientType.RTU:
            return self.get_modbus_serial_client()
        elif self.client_type == ModbusClientType.TCP:
            return self.get_modbus_tcp_client()
        else:
            raise Exception(f"Invalid Modbus Hardware specification {self.client_type}")


    def create_read_message(self, register, slave_id) -> Tuple[bytes, int]:
        """ creates the message that the hardware is expecting """
        pass


