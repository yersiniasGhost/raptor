from typing import Tuple, Union, Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass
from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.framer import FramerType
from hardware.hardware_base import HardwareBase
from hardware.modbus.modbus_map import ModbusMap, ModbusRegister, ModbusDatatype, ModbusRegisterType
from hardware.hardware_lock import modbus_lock, get_resource_key_for_modbus, HardwareLockTimeout, HardwareLockError
from utils import LogManager, check_interface, set_tcp_interface
from database.db_utils import add_hardware_state, get_previous_hardware_state
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

    # State management implementation
    def set_operational_state(self, state_name: str, parameter_overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """Set the operational state of the modbus hardware"""
        if not self.hardware_id:
            return {"success": False, "error": "Hardware ID not set"}

        # Load states configuration
        states_config = self.load_states_config()
        if not states_config:
            return {"success": False, "error": "No states configuration available"}

        # Check if state exists
        available_states = states_config.get("states", {})
        if state_name not in available_states:
            return {"success": False, "error": f"State '{state_name}' not found in configuration"}

        state_config = available_states[state_name]
        self.logger.info(f"Change state: {state_name}")

        # Validate state change
        validation_result = self.validate_state_change(state_name)
        self.logger.info(f"Validation: {validation_result}")
        if not validation_result["success"]:
            return validation_result

        # Use hardware locking for the entire state change operation
        try:

            # Store current register values for fallback rollback
            rollback_values = {}

            try:
                # Read current values before making changes
                for register_config in state_config.get("registers", []):
                    register_name = register_config["register_name"]
                    register = self.modbus_map.get_register_by_name(register_name)
                    if register:
                        # Use the first device for reading current state
                        current_values = modbus_data_read(self, register_name, slave_id=register.slave_id or 1)
                        if register_name in current_values:
                            rollback_values[register_name] = current_values[register_name]

                # Apply all register changes
                self.logger.info(f"Got rollback values: {rollback_values}")
                failed_writes = []
                parameter_overrides = parameter_overrides or {}

                for register_config in state_config.get("registers", []):
                    register_name = register_config["register_name"]
                    # Use override value if provided, otherwise use default from config
                    value = parameter_overrides.get(register_name, register_config["value"])
                    register = self.modbus_map.get_register_by_name(register_name)

                    if not register:
                        failed_writes.append(f"Register {register_name} not found in modbus map")
                        continue

                    # Perform the write
                    write_result = modbus_data_write(self, register_name, slave_id=register.slave_id or 1, value=value)
                    if not write_result.get("success", False):
                        failed_writes.append(
                            f"Failed to write {register_name}: {write_result.get('error', 'Unknown error')}")

                # If any writes failed, perform hybrid rollback
                if failed_writes:
                    self.logger.error(f"State change failed, attempting rollback: {failed_writes}")
                    self._perform_hybrid_rollback(rollback_values)
                    return {"success": False, "error": f"State change failed: {'; '.join(failed_writes)}"}

                # Record successful state change in database
                success = add_hardware_state(self.hardware_id, state_name, self.logger)
                if not success:
                    self.logger.warning("Failed to record state change in database")
                self.logger.info("State change successful")
                return {"success": True, "state": state_name, "message": f"Successfully set state to {state_name}"}

            except Exception as e:
                self.logger.error(f"Unexpected error during state change: {e}")
                # Attempt hybrid rollback on unexpected error
                self._perform_hybrid_rollback(rollback_values)
                return {"success": False, "error": f"Unexpected error: {str(e)}"}

        except HardwareLockTimeout:
            self.logger.error(f"Timeout waiting for modbus lock for state change to {state_name}")
            return {"success": False, "error": "Timeout waiting for hardware access"}
        except HardwareLockError as e:
            self.logger.error(f"Hardware lock error during state change to {state_name}: {e}")
            return {"success": False, "error": f"Hardware lock error: {str(e)}"}



    def _perform_hybrid_rollback(self, rollback_values: Dict[str, Any]):
        """Perform hybrid rollback: try previous state first, fallback to stored values"""
        try:
            # Primary rollback: revert to previous state
            previous_state = get_previous_hardware_state(self.hardware_id, self.logger)
            if previous_state:
                self.logger.info(f"Attempting rollback to previous state: {previous_state}")
                # Recursive call but with previous state - should not fail validation
                result = self.set_operational_state(previous_state)
                if result.get("success", False):
                    self.logger.info("Successfully rolled back to previous state")
                    return
                else:
                    self.logger.warning(f"Previous state rollback failed: {result.get('error', 'Unknown error')}")

            # Fallback rollback: restore individual register values
            self.logger.info("Attempting fallback rollback using stored values")
            for register_name, rollback_value in rollback_values.items():
                try:
                    register = self.modbus_map.get_register_by_name(register_name)
                    if register:
                        modbus_data_write(self, register_name, slave_id=register.slave_id or 1, value=rollback_value)
                        self.logger.debug(f"Restored {register_name} to {rollback_value}")
                except Exception as e:
                    self.logger.error(f"Failed to restore {register_name}: {e}")

        except Exception as e:
            self.logger.error(f"Rollback failed completely: {e}")



    def validate_state_change(self, state_name: str) -> Dict[str, Any]:
        """Validate if a state change is possible given current conditions"""
        states_config = self.load_states_config()
        if not states_config:
            return {"success": False, "error": "No states configuration available"}

        available_states = states_config.get("states", {})
        if state_name not in available_states:
            return {"success": False, "error": f"State '{state_name}' not found"}

        state_config = available_states[state_name]
        validation_config = state_config.get("validation", {})
        pre_checks = validation_config.get("pre_checks", [])

        # Perform pre-flight checks
        for check in pre_checks:
            register_name = check["register_name"]
            register = self.modbus_map.get_register_by_name(register_name)

            if not register:
                return {"success": False, "error": f"Validation register {register_name} not found"}

            # Read current value
            current_values = modbus_data_read(self, register_name, slave_id=register.slave_id or 1)
            if register_name not in current_values:
                return {"success": False, "error": f"Could not read validation register {register_name}"}

            current_value = current_values[register_name]

            # Check minimum value if specified
            if "min_value" in check and current_value < check["min_value"]:
                return {
                    "success": False,
                    "error": f"Validation failed: {check['description']} (current: {current_value}, required: >= {check['min_value']})"
                }

            # Check maximum value if specified
            if "max_value" in check and current_value > check["max_value"]:
                return {
                    "success": False,
                    "error": f"Validation failed: {check['description']} (current: {current_value}, required: <= {check['max_value']})"
                }

        return {"success": True, "message": "Validation passed"}



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
        return {"success": False, "error": f"Register {register_name} not found"}

    # Use hardware locking to prevent concurrent access
    try:
        with modbus_lock(modbus_hardware, timeout=30.0,
                         lock_info=f"write {register_name}={value}"):

            client = modbus_hardware.get_modbus_client()
            if not client.connect():
                logger.error("Modbus client not connected... resetting")
                modbus_hardware.reset_hardware()
                return {"success": False, "error": "Cannot connect to modbus client"}

            try:
                if register.slave_id:
                    slave_id = register.slave_id

                # Convert value based on register data type
                write_value = int(value)  # prepare_write_value(value, register)

                logger.info(f"Attempting write - Register: {register.name}, Address: {register.address}, Type: {register.type}, Slave: {slave_id}, Value: {write_value}")

                result = None
                if ModbusRegisterType(register.type) == ModbusRegisterType.HOLDING:
                    logger.info(f"Writing HOLDING register: {register.address}, Slave ID{slave_id}, {register.name}")
                    result = client.write_register(register.address, write_value, slave=slave_id)
                elif ModbusRegisterType(register.type) == ModbusRegisterType.INPUT:
                    logger.error(f"Cannot write to INPUT register (read-only): {register.address}, {register.name}")
                    return {"success": False, "error": "INPUT registers are read-only"}
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
            finally:
                try:
                    client.close()
                except:
                    pass

    except HardwareLockTimeout:
        logger.error(f"Timeout waiting for modbus lock to write {register_name}")
        return {"success": False, "error": "Timeout waiting for hardware access"}
    except HardwareLockError as e:
        logger.error(f"Hardware lock error writing {register_name}: {e}")
        return {"success": False, "error": f"Hardware lock error: {str(e)}"}


def modbus_data_read(modbus_hardware: ModbusHardware, register_key: str, slave_id: int,
                     logger=None) -> Dict[str, Union[float, int]]:
    """
    This method queries the modbus hardware based upon the slave_id and the provided register NAME.
    The output is in the format of a dictionary:   { register_name: register_value }
    """
    if not logger:
        logger = LogManager().get_logger("ModbusHardware")

    register = modbus_hardware.modbus_map.get_register_by_name(register_key)
    if not register:
        logger.error(f"Cannot find register {register_key}")
        return {}

    # Use hardware locking to prevent concurrent access
    try:
        with modbus_lock(modbus_hardware, timeout=2.0, lock_info=f"read {register_key}"):

            client = modbus_hardware.get_modbus_client()
            if not client.connect():
                logger.error("Modbus client not connected... resetting")
                modbus_hardware.reset_hardware()
                return {}

            try:
                if register.slave_id:
                    slave_id = register.slave_id
                output: Dict[str, Union[float, int]] = {}
                address = int(register.address)
                try:
                    # In some cases, like Inview S the slave ID is used to query different systems not devices
                    if register.slave_id:
                        slave_id = register.slave_id
                    result = None
                    if ModbusRegisterType(register.type) == ModbusRegisterType.HOLDING:
                        logger.info(f"Reading HOLDING register: {address}, slaveID: {slave_id}, {register.name}")
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
                        output[register_key] = convert_register_value(modbus_hardware, result.registers, register, register_key)
                except Exception as e:
                    logger.exception(f"Error reading modbus: {e} on slave: {slave_id}, {address}.. .continuing.", exc_info=True)
                return output

            finally:
                try:
                    client.close()
                except:
                    pass

    except HardwareLockTimeout:
        logger.error(f"Timeout waiting for modbus lock to read {register_key}")
        return {}
    except HardwareLockError as e:
        logger.error(f"Hardware lock error reading {register_key}: {e}")
        return {}


def modbus_data_acquisition(modbus_hardware: ModbusHardware,
                            registers: Dict[str, ModbusRegister], slave_id: int,
                            logger=None) -> Dict[str, Union[float, int]]:
    """
    This method queries the modbus hardware based upon the slave_id and the provided registers.
    The output is in the format of a dictionary:   { register_name: register_value }
    """
    if not logger:
        logger = LogManager().get_logger("ModbusHardware")

    # Use hardware locking to prevent concurrent access
    register_list = list(registers.keys())
    try:
        with modbus_lock(modbus_hardware, timeout=30.0,
                        lock_info=f"acquisition {len(register_list)} registers"):

            client = modbus_hardware.get_modbus_client()
            try:
                if not client.connect():
                    logger.error("Modbus client not connected... resetting")
                    modbus_hardware.reset_hardware()
                    return {}

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

    except HardwareLockTimeout:
        logger.error(f"Timeout waiting for modbus lock for data acquisition")
        return {}
    except HardwareLockError as e:
        logger.error(f"Hardware lock error during data acquisition: {e}")
        return {}


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

