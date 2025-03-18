from dataclasses import dataclass


@dataclass
class GenerationState:
    power_generated: float = 0
    power_curtailed: float = 0
    energy_generated: float = 0
    energy_curtailed: float = 0


@dataclass
class LoadState:
    power_demand: float = 0
    energy_demand: float = 0
    power_from_bess: float = 0
    energy_from_bess: float = 0
    power_from_gen: float = 0
    energy_from_gen: float = 0
    power_from_utility: float = 0
    energy_from_utility: float = 0


@dataclass
class BessState:
    discharge_power: float = 0
    charge_power: float = 0
    discharge_energy: float = 0
    charge_energy: float = 0
    engaged_time_s: float = 0
    state_of_charge: float = 0
