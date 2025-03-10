from typing import NamedTuple

'''
ka is the absolute scaling factor, which is equal to the efficiency at reference conditions.
This factor allows the model to be used with relative or absolute efficiencies, and to
accommodate data sets which are not perfectly normalized but have a slight bias at the
reference conditions.
• kd is the dark irradiance or diode coefficient which influences how voltage increases with
irradiance.
• tcd is the temperature coefficient of the diode coefficient, which indirectly influences
voltage. Because it is the only temperature coefficient in the model, its value will also
reflect secondary temperature dependencies that are present in the PV module.
• k_rs and k_rsh are the series and shunt resistance loss factors. Because of the normalization
they can be read as power loss fractions at reference conditions. For example, if k_rs is
0.05, the internal loss assigned to the series resistance has a magnitude equal to 5% of the
module output
'''

# Move to central location
ADR_MODEL_TYPE = "ADR"


class ADRModel(NamedTuple):
    k_a: float = 0.99924
    k_d: float = -5.49097
    tc_d: float = 0.01918
    k_rs: float = 0.06999
    k_rsh: float = 0.26144
