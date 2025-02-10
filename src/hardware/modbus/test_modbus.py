import os
from pymodbus.client import ModbusSerialClient
from pymodbus.framer import FramerType
from pymodbus.exceptions import ModbusException
import serial.tools.list_ports
import time


def check_serial_port(port):
    """Check if serial port exists and is accessible"""
    print(f"\n=== Checking Serial Port {port} ===")

    # Check if port exists
    if not os.path.exists(port):
        print(f"Error: Port {port} does not exist!")
        return False

    # List all available ports
    print("\nAvailable ports:")
    ports = serial.tools.list_ports.comports()
    for p in ports:
        print(f"- {p.device}")

    # Check permissions
    try:
        access = os.access(port, os.R_OK | os.W_OK)
        print(f"\nPort {port} accessible: {access}")
        if not access:
            print(f"Current permissions: {oct(os.stat(port).st_mode)[-3:]}")
    except Exception as e:
        print(f"Error checking permissions: {e}")
        return False

    return True


def test_modbus_connection(port='/dev/ttyS11', slave_id=1, register_address=1560):
    """
    Test Modbus RTU connection with debug information
    """
    print("\n=== Starting Modbus RTU Debug Test ===")

    # Check port first
    if not check_serial_port(port):
        return

    # Create Modbus RTU client with debug enabled
    print("\n=== Creating Modbus Client ===")
    client = ModbusSerialClient(
        port=port,
        framer=FramerType.RTU,
        baudrate=9600,
        parity='N',
        stopbits=1,
        bytesize=8,
        timeout=2,  # Increased timeout for debugging
        retries=3
    )

    #print(f"Client configuration:")
    #print(f"- Port: {client.params.port}")
    #print(f"- Baudrate: {client.params.baudrate}")
    #print(f"- Parity: {client.params.parity}")
    #print(f"- Stopbits: {client.params.stopbits}")
    #print(f"- Bytesize: {client.params.bytesize}")

    try:
        # Try to connect
        print("\n=== Attempting Connection ===")
        connection = client.connect()
        print(f"Connection result: {connection}")

        if not connection:
            print("Failed to connect!")
            return

        # Try several test reads with delays
        for attempt in range(3):
            print(f"\n=== Read Attempt {attempt + 1} ===")
            print(f"Reading register {register_address} from slave {slave_id}")

            try:
                result = client.read_holding_registers(
                    address=register_address,
                    count=1,
                    slave=slave_id
                )

                if result is None:
                    print("No response received (result is None)")
                elif hasattr(result, 'isError') and result.isError():
                    print(f"Error reading register: {result}")
                else:
                    print(f"Success! Register value: {result.registers[0]}")

            except ModbusException as me:
                print(f"Modbus error: {me}")
            except Exception as e:
                print(f"Unexpected error: {e}")

            # Wait between attempts
            time.sleep(1)

    except Exception as e:
        print(f"Error during testing: {e}")

    finally:
        print("\n=== Cleaning Up ===")
        client.close()
        print("Connection closed")


if __name__ == "__main__":
    # Try both RS-485 ports on COM2
    print("Testing first RS-485 port...")
    test_modbus_connection(
        port='/dev/ttyS11',
        slave_id=0,  # Try changing this if device address is different
        register_address=2
    )
