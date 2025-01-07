from pymodbus.client import ModbusSerialClient
from pymodbus.framer import FramerType
import binascii
import time

# CRC Tables as specified in the document
AUCHCRCHI = [
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40,  # ... truncated for brevity
]

AUCHCRCLO = [
    0x00, 0xC0, 0xC1, 0x01, 0xC3, 0x03, 0x02, 0xC2, 0xC6, 0x06, 0x07, 0xC7,
    0x05, 0xC5, 0xC4, 0x04,  # ... truncated for brevity
]


def calculate_crc(message):
    """
    Calculate CRC exactly as specified in the document
    """
    crc_hi = 0xFF  # High byte of CRC initialized
    crc_lo = 0xFF  # Low byte of CRC initialized

    for byte in message:
        index = crc_lo ^ byte
        crc_lo = crc_hi ^ AUCHCRCHI[index]
        crc_hi = AUCHCRCLO[index]

    return (crc_hi << 8 | crc_lo)


def test_bms_communication(port='/dev/ttyS11', slave_id=1):
    """
    Test BMS communication using specified parameters
    """
    # Create Modbus client with exact specifications from document
    client = ModbusSerialClient(
        port=port,
        framer=FramerType.RTU,
        baudrate=9600,  # Default as specified
        parity='N',  # No parity as specified
        stopbits=1,  # 1 stop bit as specified
        bytesize=8,  # 8 data bits as specified
        timeout=0.2  # 200ms as specified
    )

    try:
        if not client.connect():
            print("Failed to connect!")
            return

        print(f"Connected to {port}")

        # Test reading registers (starting from 0x0000 as per spec)
        registers_to_read = [
            (0x0000, "Current (10mA)"),
            (0x0001, "Voltage of pack (10mV)"),
            (0x0002, "SOC (%)"),
            (0x0003, "SOH (%)"),
            (0x0004, "Remain capacity (10mAH)"),
            (0x0005, "Full capacity (10mAH)")
        ]

        for register, description in registers_to_read:
            print(f"\nReading {description}")
            # Create the message as per specification
            message = bytes([
                slave_id,  # Slave Address (0x01-0x10)
                0x03,  # Function Code (Read Registers)
                register >> 8,  # Starting Address (Hi)
                register & 0xFF,  # Starting Address (Lo)
                0x00,  # Number of Registers (Hi)
                0x01  # Number of Registers (Lo)
            ])

            # Calculate CRC per specification
            crc = calculate_crc(message)
            print(f"Message: {binascii.hexlify(message).decode()}")
            print(f"Calculated CRC: {hex(crc)}")

            # Attempt to read
            result = client.read_holding_registers(
                address=register,
                count=1,
                slave=slave_id
            )

            if result is None:
                print("No response received")
            elif hasattr(result, 'isError') and result.isError():
                print(f"Error reading register: {result}")
            else:
                print(f"Value: {result.registers[0]}")

            # Wait for frame interval as specified (>100ms)
            time.sleep(0.1)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    # Test with default slave ID 1 (0x01)
    test_bms_communication()