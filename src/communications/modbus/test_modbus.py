from pymodbus.client import ModbusSerialClient
from pymodbus.framer import FramerType
import time


def test_modbus_connection(port='/dev/ttyS11', slave_id=1, register_address=1560):
    """
    Test Modbus RTU connection and read a register

    Args:
        port (str): Serial port (ttyS11 or ttyS12 for COM2 RS-485)
        slave_id (int): Modbus slave ID
        register_address (int): Register address to read
    """
    # Create Modbus RTU client
    client = ModbusSerialClient(
        port=port,  # Serial port
        framer=FramerType.RTU,  # RTU framer
        baudrate=9600,  # Baud rate (adjust as needed)
        parity='N',  # Parity (N for none)
        stopbits=1,  # Stop bits
        bytesize=8,  # Bits per byte
        timeout=1  # Timeout in seconds
    )

    try:
        # Connect to the device
        if not client.connect():
            print("Failed to connect!")
            return

        print(f"Connected to {port}")

        # Try to read one register
        print(f"Attempting to read register {register_address} from slave {slave_id}...")
        result = client.read_holding_registers(
            address=register_address,
            count=1,
            slave=slave_id
        )

        # Check if read was successful
        if hasattr(result, 'isError') and result.isError():
            print(f"Error reading register: {result}")
        else:
            print(f"Register value: {result.registers[0]}")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        client.close()
        print("Connection closed")


if __name__ == "__main__":
    # Test connection - adjust slave_id and register_address as needed
    test_modbus_connection(
        port='/dev/ttyS11',  # First RS-485 port on COM2
        slave_id=1,  # Change to match your device's slave ID
        register_address=2  # Change to a valid register on your device
    )