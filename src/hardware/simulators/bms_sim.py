from typing import NamedTuple, List, Dict, Any, Optional, Tuple
import pandas as pd
from hardware.hardware_base import HardwareBase
from hardware.simulators.simulation_state import SimulationState, REMAINING_CAPACITY, STATE_OF_CHARGE
from hardware.simulators.simulation_state import CURRENT, VOLTAGE
from hardware.simulators.component_states import LoadState, GenerationState, BessState
from utils.logger import LogManager


class BatterySystem(NamedTuple):
    capacity: float             # kWh of capacity
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    # The "C rating" of a battery is a measure used to describe its discharge rate capability relative to its capacity.
    c_rate_discharge: float = 2.0
    c_rate_charge: float = 1.0
    depth_of_discharge: float = 0.8  # 80% DoD for Li-Ion

    model_type: str = "RiseBatteryStorage"
    model_parameters: Dict = {"soc_charge_efficiency": 0.05, "temperature_charge_impact": 0.0001,
                              "soc_discharge_efficiency": 0.05, "temperature_discharge_impact": 0.0001}

    def get_model_param(self, name: str):
        return self.model_parameters.get(name)


class BMSSim(HardwareBase):

    def __init__(self, battery_system: dict):
        self.logger = LogManager().get_logger("BMSSim")
        self.battery_system = BatterySystem(**battery_system)
        self.state_of_charge = 0.69
        self.energy_change: float = 0
        self.power_rate: float = 0
        self.time_engaged_s: int = 0
        self.timestamp: Optional[pd.Timestamp] = None
        self._can_discharge = True
        self._can_charge = True
        self.charge_from_grid: bool = False
        self.charged_from_grid: bool = False
        self.maximum_discharge_rate: float = 1e9
        self.time_duration = 30 / 3600
        self.operating_state = 1
        self.hardware_id: str = ""



    def available_charge_power(self) -> float:
        return (1.0 - self.state_of_charge) * self.battery_system.capacity * self.battery_system.c_rate_charge

    def available_discharge_power(self) -> float:
        if self.state_of_charge <= 1.0 - self.battery_system.depth_of_discharge + 1e-5:
            return 0.0
        return min(self.maximum_discharge_rate, self.battery_system.capacity * self.battery_system.c_rate_discharge)

    def charge_eff(self, soc: float, temp: float):
        # Example charge efficiency function (modify as needed)
        sce = self.battery_system.get_model_param("soc_charge_efficiency")
        tci = self.battery_system.get_model_param("temperature_charge_impact")
        return self.battery_system.charge_efficiency + sce * soc - tci  * (temp - 25)

    def discharge_eff(self, soc: float, temp: float):
        tdi = self.battery_system.get_model_param("temperature_discharge_impact")
        sde = self.battery_system.get_model_param("soc_discharge_efficiency")
        return self.battery_system.discharge_efficiency + sde * (1.0 - soc) - tdi * (temp - 25)


    def calculate_maximum_time_of_charge(self, change_soc: float, power: float, battery_temp: float = 25.0):
        if power == 0.0:
            return 0
        max_delta_soc = 1.0 - self.state_of_charge
        max_delta_soc = 0.0 if abs(max_delta_soc) < 1e-3 else max_delta_soc
        soc = min(max_delta_soc, change_soc)
        return soc * self.battery_system.capacity * self.charge_eff(self.state_of_charge, battery_temp) / power

    def calculate_maximum_time_of_discharge(self, delta_soc: float, power: float, battery_temp: float):
        if power == 0.0:
            return 0
        max_delta_soc = self.state_of_charge - (1.0 - self.battery_system.depth_of_discharge)
        max_delta_soc = 0.0 if abs(max_delta_soc) < 1e-5 else max_delta_soc
        delta_soc = min(max_delta_soc, delta_soc)
        return delta_soc * self.battery_system.capacity * self.discharge_eff(self.state_of_charge, battery_temp) / power

    '''
    # Use the incoming power to charge the batteries.
    # If there's excess power, return the power we can track potentially wasted power
    Args: 
    Returns: Tuple:
        demand: The amount of power discharged from the battery (transient)
        duration: the time the power was discharged in seconds.
        energy: The amount of energy charging the batteries
    '''
    def charge_batteries(self, provided_power: float,  charge_from_grid: float, battery_temp: float = 25) -> float:

        # Cannot charge past 100%
        max_delta_soc = 1.0 - self.state_of_charge
        if max_delta_soc <= 1e-5:
            return provided_power

        available_charge_kw = self.available_charge_power()
        if not charge_from_grid:
            power = min(available_charge_kw, provided_power)
        else:
            power = min(available_charge_kw, charge_from_grid)
        if power == 0.0 and not charge_from_grid:
            self.logger.warning(f"WHY is power 0.0?  {self.available_charge_power()} and {provided_power}")
            return power

        soc_final, energy_flow, time_duration, used_power = self.calculate_charging(self.time_duration, max_delta_soc, power, battery_temp)
        prev_soc = self.state_of_charge
        self.state_of_charge = soc_final
        if charge_from_grid:
            self.logger.warning("UTILITY charging not implemented!")
        self.logger.info(f"Charging batteries:  Power in: {power:.2f} kW,  "
                         f"final SOC: {self.state_of_charge:.4f}, previous SOC: {prev_soc:.4f} "
                         f"charge_rate: {used_power:.3f} kW,  for: {time_duration:.2} hours")
        return used_power



    def calculate_charging(self, time_duration: float, max_delta_soc, power, battery_temp) -> Tuple[float, float, float, float]:
        max_time_of_charge = self.calculate_maximum_time_of_charge(max_delta_soc, power, battery_temp)
        time_duration = min(time_duration, max_time_of_charge)

        soc_mid = self.state_of_charge + power * time_duration / (2 * self.battery_system.capacity)
        energy_flow = power * time_duration * (self.charge_eff(self.state_of_charge, battery_temp) +
                                               self.charge_eff(soc_mid, battery_temp)) / 2
        soc_final = self.state_of_charge + energy_flow / self.battery_system.capacity
        return soc_final, energy_flow, time_duration, energy_flow/time_duration



    '''
    Args: 
    Returns: Tuple:
        demand: The amount of power discharged from the battery (transient)
        duration: the time the power was discharged in seconds.
        energy: discharged from the batteries
    '''
    def discharge_batteries(self, requested_demand: float, time_duration_seconds: float, now: pd.Timestamp,
                            battery_temp: float = 25.0) -> Tuple[float, float, float]:

        # Cannot discharge past the depth of discharge constraint
        prev_soc = self.state_of_charge
        max_delta_soc = self.state_of_charge - (1.0 - self.battery_system.depth_of_discharge)
        time_duration = time_duration_seconds / 3600.0
        if max_delta_soc <= 1e-5 or abs(requested_demand) < 1e-6:
            self.set_state(prev_soc, 0.0, 0.0, int(time_duration * 3600), 0, now)
            return 0.0, 0.0, 0.0

        # Cannot supply more than we can deliver based upon battery C-rate
        demand = min(self.available_discharge_power(), requested_demand)
        max_time_of_discharge = self.calculate_maximum_time_of_discharge(max_delta_soc, demand, battery_temp)
        time_duration = min(time_duration, max_time_of_discharge)

        soc_mid = (self.state_of_charge - demand * time_duration /
                   (2 * self.battery_system.capacity * self.discharge_eff(self.state_of_charge, battery_temp)))
        soc_mid = max(1.0-self.battery_system.depth_of_discharge, soc_mid)
        energy_flow = demand * time_duration * (1 / self.discharge_eff(self.state_of_charge, battery_temp) + 1 /
                                                self.discharge_eff(soc_mid, battery_temp)) / 2
        soc_final = self.state_of_charge - energy_flow / self.battery_system.capacity
        self.state_of_charge = soc_final

        self.set_state(soc_final, -demand, -energy_flow, int(time_duration * 3600), 0, now)
        return demand, time_duration * 3600.0, energy_flow


    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        return {d['mac']: f"NA-{d['mac']}" for d in devices}

    def _calculate_bess_interaction(self, bess_state: BessState, load_state: LoadState, power_to_from_batteries: float):
        self.state_of_charge = SimulationState().get_previous("BMS", self.hardware_id)[REMAINING_CAPACITY] / 100.0
        if power_to_from_batteries > 0 or self.charge_from_grid:
            if self._can_charge:
                bess_state.charge_power = self.charge_batteries(power_to_from_batteries, self.charge_from_grid)
                bess_state.state_of_charge = self.state_of_charge


    def data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str], hardware_id: str) -> Dict[str, Any]:
        self.hardware_id = hardware_id
        voltage = 52.0
        gen_state = GenerationState()
        load_state = LoadState()
        bess_state = BessState()

        pv_state = SimulationState().get_state("PV")
        load_data = SimulationState().get_state("Meter")

        pv_power = 0
        for hardware_id, device_data in pv_state.items():
            for device_id, data in device_data.items():
                pv_power += data.get("Power", 0.0)
        gen_state.power_generated = pv_power

        load_demand = 0.0
        for hardware_id, device_data in load_data.items():
            for device_id, data in device_data.items():
                load_demand += data.get("Demand", 0.0)
        load_state.power_demand = load_demand

        # There are different "operational priorities" to abide by:
        if self.operating_state == 1:  # PV to LOAD priority
            load_state.power_from_gen = min(pv_power, load_demand)
            pv_power -= load_state.power_from_gen
            load_demand -= load_state.power_from_gen
            power_to_from_batteries = pv_power - load_demand
            self._calculate_bess_interaction(bess_state, load_state, power_to_from_batteries)

        soc = bess_state.state_of_charge
        device_id = "BMS1"
        output = {device_id: {REMAINING_CAPACITY: soc * 100.0,
                              STATE_OF_CHARGE: int(soc * 100.0),
                              CURRENT: bess_state.charge_power / voltage,
                              VOLTAGE: voltage
                              }
                  }
        print("BMS USES THIS:", output)
        return output

    def get_points(self, names: List[str]) -> List:
        return []

