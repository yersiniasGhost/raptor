from pymodbus.client import ModbusSerialClient
from pymodbus.framer import FramerType
import binascii
import logging
import sys

# Set up logging to show Modbus messages
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

 

def calculate_crc(data):
    """Calculate CRC16 for Modbus RTU"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def print_message_with_crc(slave_id, function_code, register_address, register_count):
    """Print the complete Modbus RTU message with CRC"""
    # Build the message without CRC
    message = bytes([
        slave_id,  # Slave ID
        function_code,  # Function code (3 for read holding registers)
        register_address >> 8,  # Register address high byte
        register_address & 0xFF,  # Register address low byte
        register_count >> 8,  # Count high byte
        register_count & 0xFF  # Count low byte
    ])

    # Calculate CRC
    crc = calculate_crc(message)

    # Complete message with CRC
    complete_message = message + bytes([crc & 0xFF, crc >> 8])

    print("\nModbus RTU Message Analysis:")
    print(f"Message without CRC: {binascii.hexlify(message).decode()}")
    print(f"Calculated CRC: {hex(crc)}")
    print(f"Complete message: {binascii.hexlify(complete_message).decode()}")
    print("\nMessage breakdown:")
    print(f"Slave ID: {hex(slave_id)}")
    print(f"Function Code: {hex(function_code)}")
    print(f"Register Address: {hex(register_address)} ({register_address})")
    print(f"Register Count: {hex(register_count)} ({register_count})")
    print(f"CRC (low byte, high byte): {hex(crc & 0xFF)}, {hex(crc >> 8)}")
    return complete_message


def test_modbus_with_crc(port='/dev/ttyS11', slave_id=0, register_address=2):
    """Test Modbus RTU communication with CRC checking"""

    # Show the expected message
    print("\n=== Expected Modbus RTU Message ===")
    expected_message = print_message_with_crc(slave_id, 0x03, register_address, 1)

    # Create Modbus client
    client = ModbusSerialClient(
        port=port,
        framer=FramerType.RTU,
        baudrate=9600,
        parity='N',
        stopbits=1,
        bytesize=8,
        timeout=1
    )

    try:
        if client.connect():
            print("\n=== Attempting Read with Debug ===")
            result = client.read_holding_registers(
                address=register_address,
                count=1,
                slave=slave_id
            )

            if result is None:
                print("No response received - possible CRC error")
            elif hasattr(result, 'isError') and result.isError():
                print(f"Error reading register: {result}")
            else:
                print(f"Success! Register value: {result.registers[0]}")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        client.close()


if __name__ == "__main__":
    test_modbus_with_crc()
