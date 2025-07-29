from dataclasses import dataclass
from typing import List, Dict, Tuple, Union

from .modbus_hardware import ModbusHardware, ModbusClientType


@dataclass
class InviewGateway(ModbusHardware):

    def __post_init__(self):
        super().__post_init__()
        self.client_type = ModbusClientType.TCP

    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        output = {d["mac"]: "ID is NA" for d in devices}
        return output

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

