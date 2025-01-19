
class SystemConfiguration:

    def __init__(self):
        self.actuator_config = None
        self.bms_config = None
        self.inverter_config = None
        self.generation_config = None



    def update_config(self, section: str, config: dict):
        if section == "actuator":
            self.actuator_config = config
        elif section == "bms":
            self.bms_config = config
        elif section == "inverter":
            self.inverter_config = config
        elif section == "generation":
            self.generation_config = config
        else:
            raise ValueError(f"Invalid configuration section: {section}")

