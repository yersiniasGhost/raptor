from typing import Tuple, Union, Optional, List, Dict
from enum import Enum
from dataclasses import dataclass
from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.framer import FramerType
from hardware.hardware_base import HardwareBase
from hardware.modbus.modbus_map import ModbusMap, ModbusRegister, ModbusDatatype, ModbusRegisterType


from utils import LogManager


class ModbusClientType(Enum):
    TCP = 1,
    RTU = 2,
    NA = 3


@dataclass
class ModbusHardware(HardwareBase):
    framer: FramerType = FramerType.RTU
    baudrate: int = 9600  # Default as specified
    parity: str = 'N'  # No parity as specified
    stopbits: int = 1  # 1 stop-bit as specified
    bytesize: int = 8  # 8 data bits as specified
    timeout: float = 0.2
    client_type: ModbusClientType = ModbusClientType.RTU
    host: str = ""
    port: Optional[Union[str, int]] = None
    modbus_map_path: str = ""
    _modbus_map: Optional[ModbusMap] = None

    MODBUS_SLEEP_BETWEEN_READS: float = 0.05

    def __post_init__(self):
        super().__post_init__()
        print("\n\nIN POST\n\n")
        self._modbus_map = ModbusMap.from_json(self.modbus_map_path)

    @property
    def modbus_map(self):
        if not self._modbus_map:
            self._modbus_map = ModbusMap.from_json(self.modbus_map_path)
        return self._modbus_map

    def get_points(self, names: List[str]) -> List:
        return [p for p in self.modbus_map.register_iterator(names)]


    def data_acquisition(self, devices: list, scan_group_registers: List[str], _):
        registers = [r for r in self.modbus_map.register_iterator(scan_group_registers)]
        output = {}
        for device in devices:
            slave_id = device['slave_id']
            mac = device['mac']
            output[mac] = modbus_data_acquisition(self, registers, slave_id)
        return output    



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
        return ModbusTcpClient(host=self.host, port=int(self.port))


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

    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        raise ValueError("Get identifier must be implemented by sub-class of ModbusHardware")


def convert_register_value(raw_values: List[int], register: ModbusRegister) -> Union[float, str]:
    """Convert raw register value based on data type and apply conversion factor"""
    data_type = register.data_type
    raw_value = raw_values[0]
    if data_type == ModbusDatatype.UINT16:
        # UINT16: 0 to 65535, no conversion needed
        value = raw_value & 0xFFFF  # Ensure 16-bit unsigned

    elif data_type == ModbusDatatype.INT16:
        # INT16: -32768 to 32767
        raw_value = raw_value & 0xFFFF  # Ensure 16-bit
        # Convert to signed using 2's complement
        value = (raw_value - 65536) if (raw_value & 0x8000) else raw_value
    elif data_type == ModbusDatatype.UINT8:
        # UINT8: 0 to 255
        # Assuming it's in the low byte
        value = raw_value & 0xFF  # Mask to get only lower 8 bits
    elif data_type == ModbusDatatype.INT8:
        # INT8: -128 to 127
        raw_value = raw_value & 0xFF  # Ensure 8-bit
        # Convert to signed using 2's complement
        value = (raw_value - 256) if (raw_value & 0x80) else raw_value
    elif data_type == ModbusDatatype.FLAG16:
        value = raw_value
    elif data_type == ModbusDatatype.ASCII16:
        # ASCII16: Two ASCII characters from a 16-bit register
        # Extract high byte and low byte as ASCII characters
        output = ""
        for raw_value in raw_values:
            high_byte = (raw_value >> 8) & 0xFF
            low_byte = raw_value & 0xFF
            # Convert to characters and return as string
            output += chr(high_byte) + chr(low_byte)
        return output  # Return the string directly, no conversion factor
    elif data_type == ModbusDatatype.ASCII8:
        # ASCII8: Single ASCII character from the low byte
        # Extract only the low byte as an ASCII character
        low_byte = raw_value & 0xFF
        # Convert to character and return as string
        value = chr(low_byte)
        return value
    else:
        raise ValueError(f"Unsupported data type: {data_type}")

    return value * register.conversion_factor


def modbus_data_acquisition(modbus_hardware: ModbusHardware,
                            registers: List[ModbusRegister], slave_id: int,
                            logger=None) -> Dict[str, Union[float, int]]:
    """
    This method queries the modbus hardware based upon the slave_id and the provided registers.
    The output is in the format of a dictionary:   { register_name: register_value }
    """
    if not logger:
        logger = LogManager().get_logger("ModbusHardware")

    client = modbus_hardware.get_modbus_client()
    try:
        if not client.connect():
            logger.error("Failed to connect")
            return {}

        output: Dict[str, Union[float, int]] = {}
        for register in registers:
            address = int(register.address)
            # In some cases, like Inview S the slave ID is used to query different systems not devices
            if register.slave_id:
                slave_id = register.slave_id
            result = None
            if ModbusRegisterType(register.type) == ModbusRegisterType.HOLDING:
                logger.info(f"Reading HOLDING register: {address}, {slave_id}, {register}")
                result = client.read_holding_registers(address=address, count=register.range_size, slave=slave_id)
            else:
                logger.info(f"Reading input register: {address}, {slave_id}, {register}")
                result = client.read_input_registers(address=address, count=register.range_size, slave=slave_id)
            if result is None:
                logger.info(f"No response received from port {modbus_hardware.port}, slave: {slave_id}")
            elif hasattr(result, 'isError') and result.isError():
                logger.info(f"Error reading register: {result}")
            else:
                logger.info(f"Result is: {result.registers}")
                output[register.name] = convert_register_value(result.registers, register)
        # output['slave_id'] = slave_id
        return output
    except Exception as e:
        logger.exception(f"Error reading modbus: {e}", exc_info=True)
        raise
    finally:
        client.close()
