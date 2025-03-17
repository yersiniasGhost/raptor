from typing import NamedTuple, List, Dict, Any, Optional, Tuple
import pandas as pd
from hardware.hardware_base import HardwareBase
from hardware.simulators.simulation_state import SimulationState
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


class BMSSim(HardwareBase):

    def __init__(self, battery_system: dict):
        self.logger = LogManager().get_logger("BMSSim")
        self.battery_system = BatterySystem(**battery_system)
        self.state_of_charge = 69.0
        self.energy_change: float = 0
        self.power_rate: float = 0
        self.time_engaged_s: int = 0
        self.timestamp: Optional[pd.Timestamp] = None
        self._can_discharge = True
        self._can_charge = True
        self.charge_from_grid: bool = False
        self.charged_from_grid: bool = False
        self.maximum_discharge_rate: float = 1e9



    def available_charge_power(self) -> float:
        return (1.0 - self.state_of_charge) * self.battery_system.capacity * self.battery_system.c_rate_charge

    def available_discharge_power(self) -> float:
        if self.state_of_charge <= 1.0 - self.battery_system.depth_of_discharge + 1e-5:
            return 0.0
        return min(self.maximum_discharge_rate, self.battery_system.capacity * self.battery_system.c_rate_discharge)

    def charge_eff(self, soc: float, temp: float):
        # Example charge efficiency function (modify as needed)
        return (self.battery_system.charge_efficiency +
                self.soc_charge_efficiency * soc - self.temperature_charge_impact * (temp - 25))

    def discharge_eff(self, soc: float, temp: float):
        return (self.battery_system.discharge_efficiency +
                self.soc_discharge_efficiency * (1.0 - soc) -
                self.temperature_discharge_impact * (temp - 25))
        # return 0.95 - 0.03 * (1 - soc) - 0.002 * (temp - 25)

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
    def charge_batteries(self, provided_power: float, charge_from_grid: float, time_duration_seconds: int,
                         now: pd.Timestamp, battery_temp: float = 25) -> Tuple[float, float, float]:

        prev_soc = self.state_of_charge
        # Cannot charge past 100%
        time_duration = time_duration_seconds / 3600.0
        max_delta_soc = 1.0 - self.state_of_charge
        if max_delta_soc <= 1e-5:
            self.set_state(prev_soc, 0.0, 0.0,  int(time_duration * 3600), 0, now)

        available_charge_kw = self.available_charge_power()
        if not charge_from_grid:
            power = min(available_charge_kw, provided_power)
        else:
            power = min(available_charge_kw, charge_from_grid)
        if power == 0.0 and not charge_from_grid:
            self.logger.warning(f"WHY is power 0.0?  {self.available_charge_power()} and {provided_power}")
            return power, time_duration * 3600, 0

        soc_final, energy_flow, time_duration = self.calculate_charging(time_duration, max_delta_soc, power, battery_temp)


        self.set_state(soc_final, power, energy_flow, int(time_duration * 3600), charge_from_grid, now)
        if charge_from_grid:
            self.logger.info("UTILITY charging!")
        self.logger.info(f"Charging batteries ({self.battery_system.id}): Power in: {power:.2f} kW,  "
                           f"final SOC: {self.state_of_charge:.4f}, previous SOC: {prev_soc:.4f} "
                           f"charge_rate: {power:.3f} kW,  for: {time_duration:.2} hours")
        return power, time_duration * 3600, energy_flow



    def calculate_charging(self, time_duration: float, max_delta_soc, power, battery_temp) -> Tuple[float, float, float]:
        max_time_of_charge = self.calculate_maximum_time_of_charge(max_delta_soc, power, battery_temp)
        time_duration = min(time_duration, max_time_of_charge)

        soc_mid = self.state_of_charge + power * time_duration / (2 * self.battery_system.capacity)
        energy_flow = power * time_duration * (self.charge_eff(self.state_of_charge, battery_temp) +
                                               self.charge_eff(soc_mid, battery_temp)) / 2
        soc_final = self.state_of_charge + energy_flow / self.battery_system.capacity
        return soc_final, energy_flow, time_duration



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


    def data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str]) -> Dict[str, Any]:
        pv_state = SimulationState().get_state("PV")
        load_state = SimulationState().get_state("Meter")
        pv_power = 0
        for hardware_id, device_data in pv_state.items():
            for device_id, data in device_data.items():
                pv_power += data.get("Power", 0.0)
        load_demand = 0.0
        for hardware_id, device_data in load_state.items():
            for device_id, data in device_data.items():
                load_demand += data.get("Demand", 0.0)


        print("BMS USES THIS:", pv_power)
        print(pv_state)
        return {}

    def get_points(self, names: List[str]) -> List:
        return []

