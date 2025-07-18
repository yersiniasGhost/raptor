from typing import List, Dict
from .modbus_hardware import ModbusHardware, ModbusClientType
from .modbus_map import ModbusRegister, ModbusDatatype


class EveBattery(ModbusHardware):
    def __post_init__(self):
        self.client_type = ModbusClientType.RTU

    # Return the message and the CRC value if required.
    # def create_read_message(self, register: ModbusRegister, slave_id: int) -> Tuple[bytes, Optional[int]]:
    #     address = register.get_addresses()[0]
    #     message = bytes([
    #         slave_id,  # Slave Address (0x01-0x10)
    #         0x03,  # Function Code (Read Registers)
    #         address >> 8,  # Starting Address (Hi)
    #         address & 0xFF,  # Starting Address (Lo)
    #         0x00,  # Number of Registers (Hi)
    #         0x01  # Number of Registers (Lo)
    #     ])
    #     return message, None

    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        data = self.data_acquisition(devices, ["Model SN"], None)
        identifiers = {mac: d.get("Model_SN", "NO Local ID").rstrip() for mac, d in data.items()}
        return identifiers


    def decode_flag_status(self, register: ModbusRegister, register_value: int, key: str) -> str:
        """
        Decode BMS status register bits and return a dictionary of states
        """

        print("Register name: ", register.name)
        if key == "Warning_Flags":
            # if register.data_type == ModbusDatatype.FLAG16:
            # Dictionary to store all states
            status = {
                # Fault bits (0-7)
                'charging_mosfet_fault': bool(register_value & (1 << 0)),
                'discharging_mosfet_fault': bool(register_value & (1 << 1)),
                'temp_sensor_fault': bool(register_value & (1 << 2)),
                'battery_cell_fault': bool(register_value & (1 << 4)),
                'frontend_comm_fault': bool(register_value & (1 << 5)),

                # Status bits (8-15)
                'state_of_charge': bool(register_value & (1 << 8)),
                'state_of_discharge': bool(register_value & (1 << 9)),
                'charging_mosfet_on': bool(register_value & (1 << 10)),
                'discharging_mosfet_on': bool(register_value & (1 << 11)),
                'charging_limiter_on': bool(register_value & (1 << 12)),
                'charger_inversed': bool(register_value & (1 << 14)),
                'heater_on': bool(register_value & (1 << 15))
            }
        else:
            status = {}

        output = ""
        print("BMS Status Report:")
        print("\nFaults:")
        if any([status['charging_mosfet_fault'],
                status['discharging_mosfet_fault'],
                status['temp_sensor_fault'],
                status['battery_cell_fault'],
                status['frontend_comm_fault']]):
            if status['charging_mosfet_fault']:
                print("❌ Charging MOSFET Fault detected")
                output += "Charging MOSFET Fault, "
            if status['discharging_mosfet_fault']:
                print("❌ Discharging MOSFET Fault detected")
                output += "Discharging MOSFET Fault,"
            if status['temp_sensor_fault']:
                print("❌ Temperature Sensor Fault detected")
                output += "Temperature Sensor Fault, "
            if status['battery_cell_fault']:
                print("❌ Battery Cell Fault detected")
                output += "Battery Cell Fault, "
            if status['frontend_comm_fault']:
                print("❌ Frontend Communication Fault detected")
                output += "Frontend Communication Fault,"
        else:
            output += "No faults detected"
            print("✅ No faults detected")

        print("\nOperating Status:")
        output += " | Operating status: "
        for state in ['state_of_charge', 'state_of_discharge',
                      'charging_mosfet_on', 'discharging_mosfet_on',
                      'charging_limiter_on', 'charger_inversed','heater_on']:

            print(f"{'✓' if status[state] else '✗'} {state}")
            output += state

        return output

