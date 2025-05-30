import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import subprocess
import os
from enum import Enum
from hardware.hardware_base import HardwareBase
from utils import LogManager
import iio



class ADCRange(Enum):
    RANGE_2_5V = 0
    RANGE_10_9V = 1
    RANGE_20MA = 2


@dataclass
class ADCChannel:
    channel_number: int
    iio_channel_name: str
    gpio_voltage_select: int
    gpio_current_select: int


@dataclass
class ADCHardware(HardwareBase):
    adc_max_raw: int = 4095  # 12-bit ADC
    adc_max_voltage: float = 2.5  # Default voltage range
    gpio_bank: int = 5  # GPIO bank for ADC control
    initialized: bool = False
    iio_device_name: str = "2198000.adc"


    def __post_init__(self):
        super().__post_init__()
        self.logger = LogManager().get_logger("CT HALL")

        # Map of channel numbers to ADC channels
        self.channel_map = {
            1: ADCChannel(1, "voltage4", 10, 6),
            2: ADCChannel(2, "voltage5", 11, 7),
            3: ADCChannel(3, "voltage8", 12, 8),
            4: ADCChannel(4, "voltage9", 13, 9)
        }
        # Initialize IIO context
        try:
            self.ctx = iio.Context('local:')
            self.dev = self.ctx.find_device(self.iio_device_name)
            self.logger.info(f"Successfully initialized IIO context and found device {self.iio_device_name}")
        except Exception as e:
            self.logger.exception(f"Error initializing IIO context: {e}")
            self.ctx = None
            self.dev = None

    @classmethod
    def from_config(cls, config_dict: Dict[str, Any]) -> 'ADCHardware':
        """Create an ADCHardware instance from a configuration dictionary"""
        return cls(
            adc_max_raw=config_dict.get('adc_max_raw', 4095),
            adc_max_voltage=config_dict.get('adc_max_voltage', 2.5),
            gpio_bank=config_dict.get('gpio_bank', 5),
            iio_device_name=config_dict.get('iio_device_name', "2198000.adc")
        )

    def enable_5v_power(self):
        """Enable the 5V power output for the CTs"""
        try:
            # Enable 5V power output on P3-B pin 9 (EN_OFF_BD_5V)
            subprocess.run(["gpioset", "5", "16=1"])
            self.logger.info(f"Enabled 5V power output for CTs")
            return True
        except Exception as e:
            self.logger.exception(f"Error enabling 5V power: {e}")
            return False

    def initialize_device(self, device: Dict[str, Any]) -> bool:
        """Initialize a device's ADC channel"""
        if 'channel' not in device:
            self.logger.error(f"Missing channel in device configuration: {device}")
            return False

        channel_num = device['channel']
        if channel_num not in self.channel_map:
            self.logger.error(f"Invalid channel number {channel_num} for device {device.get('mac', 'unknown')}")
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
                subprocess.run(["gpioset", str(self.gpio_bank), f"{channel.gpio_voltage_select}=1"])
            elif adc_range == ADCRange.RANGE_10_9V:
                subprocess.run(["gpioset", str(self.gpio_bank), f"{channel.gpio_voltage_select}=1"])
            elif adc_range == ADCRange.RANGE_20MA:
                subprocess.run(["gpioset", str(self.gpio_bank), f"{channel.gpio_current_select}=1"])

            self.logger.info(f"Configured ADC channel {channel.channel_number} for range {adc_range}")
            return True
        except Exception as e:
            self.logger.exception(f"Error configuring ADC channel {channel.channel_number}: {e}")
            return False

    def read_raw_adc(self, channel_num: int) -> Optional[int]:
        """Read raw ADC value from the specified channel number using IIO"""
        if channel_num not in self.channel_map:
            self.logger.error(f"Invalid channel number: {channel_num}")
            return None

        if self.dev is None:
            self.logger.error("IIO device not initialized")
            return None

        channel = self.channel_map[channel_num]
        try:
            # Get the channel from the IIO device
            iio_channel = self.dev.find_channel(channel.iio_channel_name)
            
            # Read multiple samples and average
            total = 0.0
            n = 10
            for _ in range(n):
                raw_value = int(iio_channel.attrs['raw'].value)
                total += raw_value
                print(raw_value)
                time.sleep(0.01)  # Small delay between readings
                
            return int(total/float(n))
        except Exception as e:
            self.logger.exception(f"Error reading ADC channel {channel_num} via IIO: {e}")
            return None

    def convert_raw_to_voltage(self, raw_value: int) -> float:
        """Convert raw ADC value to voltage"""
        return (raw_value / self.adc_max_raw) * self.adc_max_voltage

    def convert_voltage_to_current(self, voltage: float, device: Dict[str, Any]) -> float:
        """Convert voltage to current for bidirectional CT with mid-supply bias"""
        # Zero-current reference point (typically 2.5V)
        zero_point = device.get('zero_point', 2.5)

        # Maximum voltage deviation from zero point (typically 0.625V for ±50A)
        max_deviation = device.get('max_deviation', 0.625)

        # Maximum current rating (typically 50A)
        max_current = device.get('max_value', 50.0)

        # Calculate current: Current = (Voltage - ZeroPoint) * (MaxCurrent/MaxDeviation)
        conversion_ratio = max_current / max_deviation
        current = (voltage - zero_point) * conversion_ratio

        # Apply any additional calibration factor and offset
        conversion_factor = device.get('conversion_factor', 1.0)
        offset = device.get('offset', 0.0)

        return current * conversion_factor + offset

    def convert_voltage_to_current_orig(self, voltage: float, device: Dict[str, Any]) -> float:
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



    def read_device(self, device: Dict[str, Any]) -> Optional[Tuple[float, float]]:
        """Read current from the specified device"""
        if 'channel' not in device:
            self.logger.error(f"Missing channel in device: {device}")
            return None

        channel_num = device['channel']
        raw_value = self.read_raw_adc(channel_num)

        if raw_value is None:
            return None

        voltage = self.convert_raw_to_voltage(raw_value)
        current = self.convert_voltage_to_current(voltage, device)

        return current, voltage

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

    def get_points(self, names: List[str]) -> List:
        """Get points for the specified names"""
        # For CT hardware, point names are directly passed through
        return names

    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        """Get identifiers for devices"""
        # Use the MAC address as the identifier
        return {device.get('mac', ''): device.get('mac', '') for device in devices}

    def data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str], hardware_id: str) -> Dict[str, Any]:
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
            self.logger.info("Initializing ADC channels for devices")
            self.enable_5v_power()
            for device in devices:
                self.initialize_device(device)
            self.initialized = True

        for device in devices:
            mac = device.get('mac')
            if not mac:
                self.logger.warning(f"Device missing MAC address: {device}")
                continue

            device_results = {}

            # Read each point in the scan group for this device
            for point in scan_group:
                # For CT hardware, points map directly to readings
                reading = self.read_device(device)
                if reading is not None:
                    current, _ = reading
                    device_results[point] = current

            result[mac] = device_results

        return result
