from dataclasses import dataclass
from typing import List, Dict

from .modbus_hardware import ModbusHardware, ModbusClientType, modbus_data_acquisition
from utils import LogManager


@dataclass
class Tristar(ModbusHardware):

    SCALING_REGISTERS = ["V_PU_hi", "V_PU_lo", "I_PU_hi", "I_PU_lo"]
    TWO_NEG_15 = 0.000030518
    TWO_NEG_16 = 0.000015259

    def __post_init__(self):
        super().__post_init__()
        self.client_type = ModbusClientType.TCP
        self.logger = LogManager().get_logger("Tristar")

    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        output = {d["mac"]: "ID is NA" for d in devices}
        return output

    def data_acquisition(self, devices: list, scan_group_registers: List[str], _):

        # First let's get the scaling registers
        self.logger.info("IN TRISTAR")
        scaling_registers = [r for r in self.modbus_map.register_iterator(self.SCALING_REGISTERS)]
        registers = [r for r in self.modbus_map.register_iterator(scan_group_registers)]
        output = {}
        for device in devices:
            slave_id = device['slave_id']
            mac = device['mac']
            scaling_values = modbus_data_acquisition(self, scaling_registers, slave_id)
            output[mac] = modbus_data_acquisition(self, registers, slave_id)
            for register_name, pre_scaled_value in output[mac].items():
                scale_function = self.modbus_map.get_register_by_name(register_name).conversion_function
                if scale_function == "voltage_scaling":
                    # TODO: Register name issue to be resolved
                    v_pu = scaling_values["Voltage_Scaling_High"] + (scaling_values["Voltage_Scaling_Low"] * self.TWO_NEG_16)
                    output[mac][register_name] = pre_scaled_value * v_pu * self.TWO_NEG_15
                elif scale_function == "current_scaling":
                    i_pu = scaling_values["Current_Scaling_High"] + (scaling_values["Current_Scaling_Low"] * self.TWO_NEG_16)
                    output[mac][register_name] = pre_scaled_value * i_pu * self.TWO_NEG_15

        return output
