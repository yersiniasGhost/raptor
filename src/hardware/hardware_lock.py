from typing import Optional
import os
from contextlib import contextmanager
from hardware.resource_lock_manager import HardwareResourceLockManager
from utils import LogManager


class HardwareLockError(Exception):
    """Exception raised when hardware lock operations fail."""
    pass


class HardwareLockTimeout(HardwareLockError):
    """Exception raised when lock acquisition times out."""
    pass


@contextmanager
def hardware_lock(resource_key: str, timeout: float = 2.0,
                 process_id: int = None, lock_info: str = None):
    """
    Context manager for exclusive hardware resource locking.

    Usage:
        with hardware_lock("modbus_rtu:/dev/ttyUSB0", timeout=30):
            # Exclusive access to modbus device
            result = modbus_data_read(...)

    Args:
        resource_key: Unique identifier for resource (e.g., "modbus_rtu:/dev/ttyUSB0")
        timeout: Maximum time to wait for lock in seconds
        process_id: Process ID requesting lock (default: current PID)
        lock_info: Optional description of lock purpose

    Raises:
        HardwareLockTimeout: If lock cannot be acquired within timeout
        HardwareLockError: If lock operation fails

    Example:
        # Modbus RTU device
        with hardware_lock("modbus_rtu:/dev/ttyUSB0"):
            data = modbus_data_read(hardware, register_name, slave_id)

        # Modbus TCP device
        with hardware_lock("modbus_tcp:192.168.1.100:502"):
            modbus_data_write(hardware, register_name, slave_id, value)

        # GPIO pin
        with hardware_lock("gpio:pin_16"):
            gpio_set_value(16, 1)

        # ADC channel
        with hardware_lock("adc:channel_0"):
            value = adc_read_channel(0)
    """
    if process_id is None:
        process_id = os.getpid()

    logger = LogManager().get_logger("HardwareLock")
    lock_manager = HardwareResourceLockManager()

    # Attempt to acquire the lock
    logger.debug(f"PID {process_id} attempting to acquire lock: {resource_key}")

    if not lock_manager.acquire_lock(resource_key, timeout, process_id, lock_info):
        raise HardwareLockTimeout(
            f"Failed to acquire lock on '{resource_key}' within {timeout} seconds"
        )

    try:
        logger.debug(f"PID {process_id} acquired lock: {resource_key}")
        yield  # Execute the protected code block
    except Exception as e:
        logger.error(f"Error while holding lock on '{resource_key}': {e}")
        raise
    finally:
        # Always release the lock
        if not lock_manager.release_lock(resource_key, process_id):
            logger.error(f"Failed to release lock on '{resource_key}' for PID {process_id}")
        else:
            logger.debug(f"PID {process_id} released lock: {resource_key}")


class HardwareLock:
    """
    Alternative class-based interface for hardware locking.

    Can be used when context manager syntax is not suitable.
    """

    def __init__(self, resource_key: str, timeout: float = 2.0,
                 process_id: int = None, lock_info: str = None):
        """
        Initialize hardware lock object.

        Args:
            resource_key: Unique identifier for resource
            timeout: Maximum time to wait for lock in seconds
            process_id: Process ID requesting lock (default: current PID)
            lock_info: Optional description of lock purpose
        """
        self.resource_key = resource_key
        self.timeout = timeout
        self.process_id = process_id if process_id is not None else os.getpid()
        self.lock_info = lock_info
        self.lock_manager = HardwareResourceLockManager()
        self.logger = LogManager().get_logger("HardwareLock")
        self._acquired = False

    def acquire(self) -> bool:
        """
        Acquire the hardware lock.

        Returns:
            bool: True if lock acquired successfully

        Raises:
            HardwareLockTimeout: If lock cannot be acquired within timeout
            HardwareLockError: If lock operation fails
        """
        if self._acquired:
            raise HardwareLockError(f"Lock already acquired for '{self.resource_key}'")

        self.logger.debug(f"PID {self.process_id} attempting to acquire lock: {self.resource_key}")

        if not self.lock_manager.acquire_lock(
            self.resource_key, self.timeout, self.process_id, self.lock_info
        ):
            raise HardwareLockTimeout(
                f"Failed to acquire lock on '{self.resource_key}' within {self.timeout} seconds"
            )

        self._acquired = True
        self.logger.debug(f"PID {self.process_id} acquired lock: {self.resource_key}")
        return True

    def release(self) -> bool:
        """
        Release the hardware lock.

        Returns:
            bool: True if lock released successfully
        """
        if not self._acquired:
            self.logger.warning(f"Attempted to release lock that wasn't acquired: {self.resource_key}")
            return False

        success = self.lock_manager.release_lock(self.resource_key, self.process_id)
        if success:
            self._acquired = False
            self.logger.debug(f"PID {self.process_id} released lock: {self.resource_key}")
        else:
            self.logger.error(f"Failed to release lock on '{self.resource_key}' for PID {self.process_id}")

        return success

    def is_acquired(self) -> bool:
        """
        Check if this lock object has acquired its lock.

        Returns:
            bool: True if lock is currently held by this object
        """
        return self._acquired

    def __enter__(self):
        """Context manager entry - acquire lock."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - release lock."""
        if self._acquired:
            self.release()


def get_resource_key_for_modbus(hardware, client_type: str = None) -> str:
    """
    Generate standard resource key for modbus hardware.

    Args:
        hardware: ModbusHardware instance
        client_type: Override client type if needed

    Returns:
        str: Standardized resource key for modbus device
    """
    if client_type is None:
        client_type = hardware.client_type.name.lower()

    if client_type == "rtu":
        return f"modbus_rtu:{hardware.port}"
    elif client_type == "tcp":
        return f"modbus_tcp:{hardware.host}:{hardware.port}"
    else:
        return f"modbus_{client_type}:{hardware.port}"


def get_resource_key_for_gpio(pin_number: int) -> str:
    """
    Generate standard resource key for GPIO pin.

    Args:
        pin_number: GPIO pin number

    Returns:
        str: Standardized resource key for GPIO pin
    """
    return f"gpio:pin_{pin_number}"


def get_resource_key_for_adc(channel: int) -> str:
    """
    Generate standard resource key for ADC channel.

    Args:
        channel: ADC channel number

    Returns:
        str: Standardized resource key for ADC channel
    """
    return f"adc:channel_{channel}"


def get_resource_key_for_electrak(device_id: str) -> str:
    """
    Generate standard resource key for Electrak device.

    Args:
        device_id: Electrak device identifier

    Returns:
        str: Standardized resource key for Electrak device
    """
    return f"electrak:{device_id}"


# Convenience functions for common resource types
def modbus_lock(hardware, timeout: float = 2.0, lock_info: str = None):
    """
    Context manager for modbus hardware locking.

    Args:
        hardware: ModbusHardware instance
        timeout: Lock timeout in seconds
        lock_info: Optional lock description

    Returns:
        Context manager for modbus lock
    """
    resource_key = get_resource_key_for_modbus(hardware)
    return hardware_lock(resource_key, timeout=timeout, lock_info=lock_info)


def gpio_lock(pin_number: int, timeout: float = 2.0, lock_info: str = None):
    """
    Context manager for GPIO pin locking.

    Args:
        pin_number: GPIO pin number
        timeout: Lock timeout in seconds
        lock_info: Optional lock description

    Returns:
        Context manager for GPIO lock
    """
    resource_key = get_resource_key_for_gpio(pin_number)
    return hardware_lock(resource_key, timeout=timeout, lock_info=lock_info)


def adc_lock(channel: int, timeout: float = 30.0, lock_info: str = None):
    """
    Context manager for ADC channel locking.

    Args:
        channel: ADC channel number
        timeout: Lock timeout in seconds
        lock_info: Optional lock description

    Returns:
        Context manager for ADC lock
    """
    resource_key = get_resource_key_for_adc(channel)
    return hardware_lock(resource_key, timeout=timeout, lock_info=lock_info)


def electrak_lock(device_id: str, timeout: float = 30.0, lock_info: str = None):
    """
    Context manager for Electrak device locking.

    Args:
        device_id: Electrak device identifier
        timeout: Lock timeout in seconds
        lock_info: Optional lock description

    Returns:
        Context manager for Electrak lock
    """
    resource_key = get_resource_key_for_electrak(device_id)
    return hardware_lock(resource_key, timeout=timeout, lock_info=lock_info)