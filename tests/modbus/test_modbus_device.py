import unittest
from pymodbus.client import ModbusTcpClient
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
import threading
import time
import socket


class TestModbusDevice:

    def __init__(self, host="localhost", port=502):
        self.store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [False] * 100),
            co=ModbusSequentialDataBlock(0, [False] * 100),
            hr=ModbusSequentialDataBlock(0, [0] * 100),
            ir=ModbusSequentialDataBlock(0, [0] * 100)
        )
        self.context = ModbusServerContext(slaves=self.store, single=True)
        self.host = host
        self.port = port
        self._running = False



    def start(self):
        """Start the server and wait for it to be ready"""
        self.server_thread = threading.Thread(
            target=self._run_server,
            daemon=True
        )
        self.server_thread.start()

        # Wait for the server to start listening
        retry_count = 0
        while retry_count < 10:  # Try for 5 seconds
            try:
                with socket.create_connection((self.host, self.port), timeout=0.5):
                    self._running = True
                    return True
            except (socket.timeout, ConnectionRefusedError):
                time.sleep(0.5)
                retry_count += 1

        raise RuntimeError("Server failed to start")



    def _run_server(self):
        """Target for the server thread"""
        StartTcpServer(
            context=self.context,
            address=(self.host, self.port)
        )



    def stop(self):
        self._running = False
        # The server will stop when the thread terminates


class ModbusTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up test device and client once for all tests"""
        cls.test_device = TestModbusDevice()
        cls.test_device.start()
        cls.client = ModbusTcpClient('localhost', port=5020)
        cls.client.connect()



    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        cls.client.close()
        cls.test_device.stop()



    def setUp(self):
        """Reset device state before each test"""
        # Reset all registers to known state
        self.client.write_registers(0, [0] * 10)
        self.client.write_coils(0, [False] * 10)



    def test_coil_operations(self):
        """Test basic coil operations"""
        # Test single coil write/read
        self.client.write_coil(0, True)
        result = self.client.read_coils(0, count=1)
        self.assertTrue(result.bits[0])

        # Test multiple coils write/read
        test_values = [True, False, True, True]
        self.client.write_coils(1, values=test_values)
        result = self.client.read_coils(1, count=len(test_values))
        self.assertEqual(list(result.bits[:len(test_values)]), test_values)



    def test_register_operations(self):
        """Test basic register operations"""
        # Test single register write/read
        test_value = 12345
        self.client.write_register(0, value=test_value)
        result = self.client.read_holding_registers(0, count=1)
        self.assertEqual(result.registers[0], test_value)

        # Test multiple registers write/read
        test_values = [111, 222, 333]
        self.client.write_registers(1, values=test_values)
        result = self.client.read_holding_registers(1, count=len(test_values))
        self.assertEqual(list(result.registers), test_values)



    def test_invalid_operations(self):
        """Test error handling for invalid operations"""
        # Test reading from invalid address
        result = self.client.read_holding_registers(999, count=1)
        self.assertTrue(result.isError())



    def test_register_ranges(self):
        """Test register value ranges"""
        # Test minimum value
        self.client.write_register(0, value=0)
        result = self.client.read_holding_registers(0, count=1)
        self.assertEqual(result.registers[0], 0)

        # Test maximum value
        self.client.write_register(0, value=65535)
        result = self.client.read_holding_registers(0, count=1)
        self.assertEqual(result.registers[0], 65535)



    def test_mock_process_simulation(self):
        """Test a simulated process control scenario"""
        # Simulate setting a temperature setpoint
        TEMP_SETPOINT_REG = 0
        CONTROL_ENABLE_COIL = 0

        # Set temperature setpoint to 75.5 (multiply by 10 to store as integer)
        self.client.write_register(TEMP_SETPOINT_REG, 755)

        # Enable control
        self.client.write_coil(CONTROL_ENABLE_COIL, True)

        # Verify settings
        setpoint = self.client.read_holding_registers(TEMP_SETPOINT_REG, count=1)
        control_enabled = self.client.read_coils(CONTROL_ENABLE_COIL, count=1)

        self.assertEqual(setpoint.registers[0], 755)
        self.assertTrue(control_enabled.bits[0])
