from typing import List, Dict, Any
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
        if key == "Status_Flags":
            status = {
                "state of charge":  bool(register_value & (1 << 8)),
                "state of discharge":  bool(register_value & (1 << 9)),
                "charging MOSFET fault":  bool(register_value & (1 << 0)),
                "discharging MOSFET fault":  bool(register_value & (1 << 1)),
                "temperature sensor fault":  bool(register_value & (1 << 2)),
                "battery cell fault":  bool(register_value & (1 << 4)),
                "front end sampling communication fault":  bool(register_value & (1 << 5)),
                "state of charging MOSFET":  bool(register_value & (1 << 10)),
                "state of discharging MOSFET":  bool(register_value & (1 << 11)),
                "charging limiter":  bool(register_value & (1 << 12)),
                "charger_inversed":  bool(register_value & (1 << 14)),
                "heater ON":  bool(register_value & (1 << 15)),
            }
            output = "Status/Fault: "
            for key, value in status.items():
                if value:
                    output += f"{key}, "
            return output
        
        if key == "Protection_Flags":
            status = {
                "battery cell over voltage": bool(register_value & (1 << 0)),
                "battery cell low voltage": bool(register_value & (1 << 1)),
                "battery pack over voltage": bool(register_value & (1 << 2)),
                "battery pack low voltage": bool(register_value & (1 << 3)),
                "charging over current": bool(register_value & (1 << 4)),
                "discharging over current": bool(register_value & (1 << 5)),
                "short circuit": bool(register_value & (1 << 6)),
                "charger over voltage": bool(register_value & (1 << 7)),
                "charging high temperature": bool(register_value & (1 << 8)),
                "discharging high temperature": bool(register_value & (1 << 9)),
                "charging low temperature": bool(register_value & (1 << 10)),
                "discharging low temperature": bool(register_value & (1 << 11)),
                "MOSFET high temperature": bool(register_value & (1 << 12)),
                "environment high temperature": bool(register_value & (1 << 13)),
                "environment low temperature": bool(register_value & (1 << 14))
            }
            output = "Protection: "
            for key, value in status.items():
                if value:
                    output += f"{key}, "
            return output
            
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

    # State management methods implementation (pass-through for now)
    def set_operational_state(self, state_name: str, parameter_overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """Set operational state - not implemented for EveBattery"""
        return {"success": False, "error": "State management not implemented for EveBattery"}


    def validate_state_change(self, state_name: str) -> Dict[str, Any]:
        """Validate state change - not implemented for EveBattery"""
        return {"success": False, "error": "State management not implemented for EveBattery"}

    def get_available_states(self) -> List[str]:
        """Get available states - not implemented for EveBattery"""
        return []

