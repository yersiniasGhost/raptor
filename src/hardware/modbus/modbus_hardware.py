from typing import Tuple, Union, Optional, List, Dict
from enum import Enum
from dataclasses import dataclass
from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.framer import FramerType
from hardware.hardware_base import HardwareBase
from hardware.modbus.modbus_map import ModbusMap, ModbusRegister, ModbusDatatype, ModbusRegisterType
from utils import LogManager, check_interface, set_tcp_interface
import time


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
    interface: Optional[str] = None
    interface_ip: Optional[str] = None
    modbus_map_path: str = ""
    _modbus_map: Optional[ModbusMap] = None

    MODBUS_SLEEP_BETWEEN_READS: float = 0.05

    def __post_init__(self):
        super().__post_init__()
        self._modbus_map = ModbusMap.from_json(self.modbus_map_path)

    @property
    def modbus_map(self):
        if not self._modbus_map:
            self._modbus_map = ModbusMap.from_json(self.modbus_map_path)
        return self._modbus_map

    def get_points(self, keys: List[str]) -> Dict[str, ModbusRegister]:
        if len(keys) == 0:
            return self.modbus_map.registers
        return self.modbus_map.get_registers_by_key(keys)


    def data_acquisition(self, devices: List[dict], scan_group_registers: List[str], _):
        registers = self.modbus_map.get_registers_by_key(scan_group_registers)
        output = {}
        for device in devices:
            slave_id = device['slave_id']
            mac = device['mac']
            output[mac] = modbus_data_acquisition(self, registers, slave_id)
        return output    

    # TCP Modbus resets/checks the interface settings
    def reset_hardware(self) -> Tuple[str, Union[str, bool]]:
        if self.client_type == ModbusClientType.TCP:
            self.logger.info(f"Resetting Modbus TCP interface on {self.interface}")
            status, info = set_tcp_interface(self.interface, self.interface_ip, self.logger)
            return (f"Modbus TCP: UP: {info['is_up']}, RUNNING: {info['is_running']}, ADDR: {info['ip_address']}",
                    info['interface_good'])
        return "Modus RTU Reset Hardware TBD", True

    def ping_hardware(self) -> Tuple[str, Union[str, bool]]:
        if self.client_type == ModbusClientType.TCP:
            self.logger.info(f"Running check on Modbus TCP interface on {self.interface}")
            status, info = check_interface(self.interface, self.logger)
            return (f"Modbus TCP: UP: {info['is_up']}, RUNNING: {info['is_running']}, ADDR: {info['ip_address']}",
                    info['interface_good'])
        return "Modus RTU Reset Hardware TBD", True


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
        return ModbusTcpClient(host=self.host, port=int(self.port), timeout=5.0)


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

    # Override this method in the base classes if needed
    def decode_flag_status(self, register, raw_value, key: str):
        print("BASE method decode_flag-status")
        return raw_value


def convert_register_value(hardware: ModbusHardware, raw_values: List[int],
                           register: ModbusRegister, key: str) -> Union[float, str]:
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
        value = hardware.decode_flag_status(register, raw_value, key)
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


def modbus_data_write(modbus_hardware: ModbusHardware,
                      register_name: str, slave_id: int, value: Union[int, float],
                      logger=None) -> Dict[str, Union[bool, str]]:

    if not logger:
        logger = LogManager().get_logger("ModbusHardware")

    register = modbus_hardware.modbus_map.get_register_by_name(register_name)
    if not register:
        logger.error(f"Cannot find register {register_name}")
        return {}

    client = modbus_hardware.get_modbus_client()
    if not client.connect():
        logger.error("Modbus client not connected... resetting")
        modbus_hardware.reset_hardware()
        return {}

    try:
        if register.slave_id:
            slave_id = register.slave_id

        # Convert value based on register data type
        write_value = int(value) # prepare_write_value(value, register)

        result = None
        if ModbusRegisterType(register.type) == ModbusRegisterType.HOLDING:
            logger.info(f"Writing HOLDING register: {register.address}, {slave_id}, {register.name}")
            result = client.write_register(register.address, write_value, slave=slave_id)
        elif ModbusRegisterType(register.type) == ModbusRegisterType.INPUT:
            logger.info(f"Writing INPUT register: {register.address}, {slave_id}, {register.name}")
            result = client.write_register(register.address, write_value, slave=slave_id)
        else:
            logger.error(f"Unsupported register type for writing: {register.type}")
            return {"success": False, "error": "Unsupported register type"}

        if result and hasattr(result, 'isError') and result.isError():
            logger.error(f"Modbus write error: {result}")
            return {"success": False, "error": f"Modbus error: {result}"}
        elif result is None:
            logger.error("No response from Modbus write operation")
            return {"success": False, "error": "No response from device"}
        return {"success": True, "register": register_name, "value": write_value}

    except Exception as e:
        logger.exception(f"Error writing modbus: {e}")
        return {"success": False, "error": str(e)}


def modbus_data_acquisition(modbus_hardware: ModbusHardware,
                            registers: Dict[str, ModbusRegister], slave_id: int,
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
            logger.error("Modbus client not connected... resetting")
            modbus_hardware.reset_hardware()

        output: Dict[str, Union[float, int]] = {}
        for key, register in registers.items():
            address = int(register.address)
            try:
                # In some cases, like Inview S the slave ID is used to query different systems not devices
                if register.slave_id:
                    slave_id = register.slave_id
                result = None
                if ModbusRegisterType(register.type) == ModbusRegisterType.HOLDING:
                    logger.info(f"Reading HOLDING register: {address}, {slave_id}, {register.name}")
                    result = client.read_holding_registers(address=address, count=register.range_size, slave=slave_id)
                else:
                    logger.info(f"Reading INPUT register: {address}, {slave_id}, {register.name}")
                    result = client.read_input_registers(address=address, count=register.range_size, slave=slave_id)

                if result is None:
                    logger.info(f"No response received from port {modbus_hardware.port}, slave: {slave_id}")
                elif hasattr(result, 'isError') and result.isError():
                    logger.info(f"Error reading register: {result}")
                    time.sleep(0.5)
                else:
                    logger.info(f"Result is: {result.registers}")
                    output[key] = convert_register_value(modbus_hardware, result.registers, register, key)
            except Exception as e:
                logger.exception(f"Error reading modbus: {e} on slave: {slave_id}, {address}.. .continuing.", exc_info=True)
        return output

    finally:
        try:
            client.close()
        except:
            pass


def modbus_data_write_different(modbus_hardware: ModbusHardware,
                      modbus_map: ModbusMap,
                      slave_id: int,
                      register_name: str,
                      value: Union[float, int],
                      logger=None) -> bool:
    if not logger:
        logger = LogManager().get_logger("ModbusHardware")

    client = modbus_hardware.get_modbus_client()
    try:
        if not client.connect():
            logger.warning("Failed to connect to Modbus client.")
            return False

        # Find the register by name
        register = modbus_map.get_register_by_name(register_name)
        if not register:
            logger.warning(f"Register {register_name} not found in map")
            return False

        if register.access != "RW":
            logger.warning(f"Cannot write, register is not RW: {register}")
            return False
        # Convert the value to the appropriate format for the register
        try:
            converted_value = prepare_value_for_register(value, register)
        except ValueError as e:
            logger.exception(f"Error converting value: {e}")
            return False

        # Attempt write to register
        address = register.get_addresses()[0]
        result = client.write_register(address=address, value=converted_value, slave=slave_id)

        if result is None:
            logger.error(f"No response received from port {modbus_hardware.port}, slave: {slave_id}")
            logger.error(f"Register was: {register}")
            return False
        elif hasattr(result, 'isError') and result.isError():
            logger.error(f"Error writing to register: {result}")
            logger.error(f"Register was: {register}")
            return False
        return True

    except Exception as e:
        logger.error(f"Error writing to modbus: {e}")
        return False
    finally:
        try:
            client.close()
        except:
            pass


def prepare_value_for_register(value: Union[float, int], register: ModbusRegister) -> int:
    """Convert a value to the appropriate format for writing to a register."""
    data_type = register.data_type
    if data_type == ModbusDatatype.INT16:
        # Ensure value is within INT16 range
        if not -32768 <= value <= 32767:
            raise ValueError(f"Value {value} out of range for INT16")
        return int(value)

    elif data_type == ModbusDatatype.UINT16:
        # Ensure value is within UINT16 range
        if not 0 <= value <= 65535:
            raise ValueError(f"Value {value} out of range for UINT16")
        return int(value)

    elif data_type == ModbusDatatype.INT8:
        # Ensure value is within INT8 range
        if not -128 <= value <= 127:
            raise ValueError(f"Value {value} out of range for INT8")
        return int(value)

    else:
        raise ValueError(f"Unsupported register type: {register.type}")
