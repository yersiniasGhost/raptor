from typing import List, Dict, Any
from .adc_hardware import ADCHardware


class CTHall(ADCHardware):

    @classmethod
    def from_config(cls, config_dict: Dict[str, Any]) -> 'CTHall':
        """Create an CTHall/ADCHardware instance from a configuration dictionary"""
        return cls(
            adc_max_raw=config_dict.get('adc_max_raw', 4095),
            adc_max_voltage=config_dict.get('adc_max_voltage', 2.5),
            gpio_bank=config_dict.get('gpio_bank', 5),
            iio_device_name=config_dict.get('iio_device_name', "2198000.adc"),
            enable_5v_pwr=config_dict.get('enable_5v_pwr', False),
            disable_pwr_between_reads=config_dict.get("disable_pwr_between_reads", True)
        )


    def data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str], hardware_id: str) -> Dict[str, Any]:
        """
        Acquire data from devices

        :param devices: List of devices to read from
        :param scan_group: List of point names to read, not required for ADC measurements
        :param hardware_id: Hardware identifier
        :return: Dictionary mapping device MACs to measurements
        """
        output = {}
        result = self.adc_data_acquisition(devices, [], hardware_id)
        for device in devices:
            mac = device.get('mac')
            voltage = result[mac]
            current = self.convert_voltage_to_current(voltage, device)
            output[mac] = {mac: current}
        return output


    def test_device(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test a device and return diagnostic information"""
        result = {
            "mac": device.get('mac', 'unknown'),
            "status": "fail",
            "raw": 0,
            "voltage": 0.0,
            "current": 0.0,
            "error": None
        }

        try:
            if 'channel' not in device:
                result["error"] = "Missing channel in device configuration"
                return result

            channel_num = device['channel']
            if channel_num not in self.channel_map:
                result["error"] = f"Invalid channel number: {channel_num}"
                return result

            raw_value = self.read_raw_adc(channel_num)
            if raw_value is None:
                result["error"] = f"Failed to read ADC channel {channel_num}"
                return result

            voltage = self.convert_raw_to_voltage(raw_value)
            current = self.convert_voltage_to_current(voltage, device)

            result["raw"] = raw_value
            result["voltage"] = voltage
            result["current"] = current
            result["status"] = "success"
            return result

        except Exception as e:
            result["error"] = str(e)
            self.logger.exception(f"Error testing device {device.get('mac', 'unknown')}: {e}")
            return result

    @staticmethod
    def convert_voltage_to_current(voltage: float, device: Dict[str, Any]) -> float:
        """Convert voltage to current for bidirectional CT with mid-supply bias"""
        # Zero-current reference point (typically 2.5V)
        zero_point = device.get('zero_point', 2.5)

        # Maximum voltage deviation from zero point (typically 0.625V for ±50A)
        max_deviation = device.get('max_deviation', 0.625)

        # Maximum current rating (typically 50A)
        max_current = device.get('max_current', 50.0)

        # Calculate current: Current = (Voltage - ZeroPoint) * (MaxCurrent/MaxDeviation)
        conversion_ratio = max_current / max_deviation
        current = (voltage - zero_point) * conversion_ratio

        # Apply any additional calibration factor and offset
        conversion_factor = device.get('conversion_factor', 1.0)
        offset = device.get('offset', 0.0)

        return current * conversion_factor + offset
