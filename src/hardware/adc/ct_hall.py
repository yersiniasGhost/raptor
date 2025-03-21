from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
import subprocess
import time
import os
import json
from enum import Enum
from hardware.hardware_base import HardwareBase
import logging

logger = logging.getLogger(__name__)


class ADCRange(Enum):
    RANGE_2_5V = 0
    RANGE_10_9V = 1
    RANGE_20MA = 2


@dataclass
class ADCChannel:
    channel_number: int
    raw_file: str
    gpio_voltage_select: int
    gpio_current_select: int


@dataclass
class ADCHardware(HardwareBase):
    adc_max_raw: int = 4095  # 12-bit ADC
    adc_max_voltage: float = 2.5  # Default voltage range
    gpio_bank: int = 5  # GPIO bank for ADC control
    initialized: bool = False



    def __post_init__(self):
        super().__post_init__()

        # Map of channel numbers to ADC channels
        self.channel_map = {
            1: ADCChannel(1, "/sys/bus/iio/devices/iio:device0/in_voltage4_raw", 10, 6),
            2: ADCChannel(2, "/sys/bus/iio/devices/iio:device0/in_voltage5_raw", 11, 7),
            3: ADCChannel(3, "/sys/bus/iio/devices/iio:device0/in_voltage8_raw", 12, 8),
            4: ADCChannel(4, "/sys/bus/iio/devices/iio:device0/in_voltage9_raw", 13, 9)
        }



    @classmethod
    def from_config(cls, config_dict: Dict[str, Any]) -> 'ADCHardware':
        """Create an ADCHardware instance from a configuration dictionary"""
        return cls(
            adc_max_raw=config_dict.get('adc_max_raw', 4095),
            adc_max_voltage=config_dict.get('adc_max_voltage', 2.5),
            gpio_bank=config_dict.get('gpio_bank', 5)
        )



    def initialize_device(self, device: Dict[str, Any]) -> bool:
        """Initialize a device's ADC channel"""
        if 'channel' not in device:
            logger.error(f"Missing channel in device configuration: {device}")
            return False

        channel_num = device['channel']
        if channel_num not in self.channel_map:
            logger.error(f"Invalid channel number {channel_num} for device {device.get('mac', 'unknown')}")
            return False

        # Configure channel for 2.5V range
        channel = self.channel_map[channel_num]
        return self.configure_adc_channel(channel, ADCRange.RANGE_2_5V)



    def configure_adc_channel(self, channel: ADCChannel, adc_range: ADCRange) -> bool:
        """Configure an ADC channel for the specified range"""
        try:
            # Disable all modes first
            subprocess.run(["gpioset", str(self.gpio_bank), f"{channel.gpio_voltage_select}=0"])
            subprocess.run(["gpioset", str(self.gpio_bank), f"{channel.gpio_current_select}=0"])

            # Set the appropriate mode
            if adc_range == ADCRange.RANGE_2_5V:
                # Default 2.5V range, already set
                pass
            elif adc_range == ADCRange.RANGE_10_9V:
                subprocess.run(["gpioset", str(self.gpio_bank), f"{channel.gpio_voltage_select}=1"])
            elif adc_range == ADCRange.RANGE_20MA:
                subprocess.run(["gpioset", str(self.gpio_bank), f"{channel.gpio_current_select}=1"])

            logger.info(f"Configured ADC channel {channel.channel_number} for range {adc_range}")
            return True
        except Exception as e:
            logger.exception(f"Error configuring ADC channel {channel.channel_number}: {e}")
            return False



    def read_raw_adc(self, channel_num: int) -> Optional[int]:
        """Read raw ADC value from the specified channel number"""
        if channel_num not in self.channel_map:
            logger.error(f"Invalid channel number: {channel_num}")
            return None

        channel = self.channel_map[channel_num]
        try:
            if not os.path.exists(channel.raw_file):
                logger.error(f"ADC file does not exist: {channel.raw_file}")
                return None

            with open(channel.raw_file, 'r') as f:
                raw_value = int(f.read().strip())
            return raw_value
        except Exception as e:
            logger.exception(f"Error reading ADC channel {channel_num}: {e}")
            return None



    def convert_raw_to_voltage(self, raw_value: int) -> float:
        """Convert raw ADC value to voltage"""
        return (raw_value / self.adc_max_raw) * self.adc_max_voltage



    def convert_voltage_to_current(self, voltage: float, device: Dict[str, Any]) -> float:
        """Convert voltage to current using device configuration"""
        # Get CT ratio (default to 20.0 for 50A/2.5V)
        ct_ratio = device.get('ct_ratio', 20.0)
        # Get conversion factor (default to 1.0)
        conversion_factor = device.get('conversion_factor', 1.0)
        # Get offset (default to 0.0)
        offset = device.get('offset', 0.0)

        # Calculate current: I = V * CT_ratio * conversion_factor + offset
        current = voltage * ct_ratio * conversion_factor + offset
        return current



    def read_device_current(self, device: Dict[str, Any]) -> Optional[float]:
        """Read current from the specified device"""
        if 'channel' not in device:
            logger.error(f"Missing channel in device: {device}")
            return None

        channel_num = device['channel']
        raw_value = self.read_raw_adc(channel_num)

        if raw_value is None:
            return None

        voltage = self.convert_raw_to_voltage(raw_value)
        current = self.convert_voltage_to_current(voltage, device)

        return current



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
            logger.exception(f"Error testing device {device.get('mac', 'unknown')}: {e}")
            return result



    def get_points(self, names: List[str]) -> List:
        """Get points for the specified names"""
        # For CT hardware, point names are directly passed through
        return names



    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        """Get identifiers for devices"""
        # Use the MAC address as the identifier
        return {device.get('mac', ''): device.get('mac', '') for device in devices}



    def data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str], hardware_id: str) -> Dict[
        str, Any]:
        """
        Acquire data from devices

        :param devices: List of devices to read from
        :param scan_group: List of point names to read
        :param hardware_id: Hardware identifier
        :return: Dictionary mapping device MACs to measurements
        """
        result = {}

        # Initialize devices if not already done
        if not self.initialized:
            logger.info("Initializing ADC channels for devices")
            for device in devices:
                self.initialize_device(device)
            self.initialized = True

        for device in devices:
            mac = device.get('mac')
            if not mac:
                logger.warning(f"Device missing MAC address: {device}")
                continue

            device_results = {}

            # Read each point in the scan group for this device
            for point in scan_group:
                # For CT hardware, points map directly to readings
                current = self.read_device_current(device)
                if current is not None:
                    device_results[point] = current

            result[mac] = device_results

        return result
