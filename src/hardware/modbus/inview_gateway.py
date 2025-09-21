from dataclasses import dataclass
from typing import List, Dict, Tuple, Union, Any

from .modbus_hardware import ModbusHardware, ModbusClientType


@dataclass
class InviewGateway(ModbusHardware):

    def __post_init__(self):
        super().__post_init__()
        self.client_type = ModbusClientType.TCP
        # Set states configuration path for Sierra25 converter states
        self.states_config_path = "data/Sierra25/sierra25_states.json"

    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        output = {d["mac"]: "ID is NA" for d in devices}
        return output

    def has_input_AC(self, devices: List[dict]) -> bool:
        ac_inputs = self.data_acquisition(devices, ['AC_input_voltage'], "")
        ac_input = False
        for dev in devices:
            if ac_inputs[dev['mac']]['AC_input_voltage'] > 90.0:
                ac_input = True
        return ac_input


    def scenario_status(self, mode: str,  devices: List[dict], hardware_id: str):
        ac_inputs = self.data_acquisition(devices,['AC_input_voltage', 'AC_input_power'], hardware_id)
        dc_bus = self.data_acquisition(devices,['DC_Voltage', 'DC_Current', "DC_Power"], hardware_id)
        converter = self.data_acquisition(devices,['Converter_DC_current', 'Converter_DC_power', 'Converter_DC_voltage'], hardware_id)
        mode = self.data_acquisition(devices,['Operating_mode'], hardware_id)
        ac_stop_power = self.data_acquisition(devices,['AC_stop_power'], hardware_id)

        for device in devices:
            print(dc_bus[device['mac']])
            print(ac_inputs[device['mac']])
            print(converter[device['mac']])
            print(mode[device['mac']])
            print(ac_stop_power[device['mac']])

    # State management methods implementation - inherits from ModbusHardware
    # The ModbusHardware base class provides full implementation
    # get_current_state inherited from HardwareBase

