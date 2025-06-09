import time
from abc import abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import subprocess
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
    adc_max_voltage: float = 10.9  # High Voltage range
    gpio_bank: int = 5  # GPIO bank for ADC control
    enable_5v_pwr: bool = False
    disable_pwr_between_reads: bool = True
    initialized: bool = False
    iio_device_name: str = "2198000.adc"
    channels_configured: bool = False


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

    @abstractmethod
    def from_config(cls, config_dict: Dict[str, Any]):
        pass
        # Sub classes of ADC hardware can implement this construction.
        # """Create an ADCHardware instance from a configuration dictionary"""
        # return cls(
        #     adc_max_raw=config_dict.get('adc_max_raw', 4095),
        #     adc_max_voltage=config_dict.get('adc_max_voltage', 2.5),
        #     gpio_bank=config_dict.get('gpio_bank', 5),
        #     iio_device_name=config_dict.get('iio_device_name', "2198000.adc"),
        #     enable_5v_pwr=config_dict.get('enable_5v_pwr', False),
        #     disable_pwr_between_reads=config_dict.get("disable_pwr_between_reads", True)
        # )


    def disable_5v_power(self):
        """Disable the 5V power output for the ADC devices """
        if not self.enable_5v_pwr:  # power wasn't required
            return True

        try:
            # Disable 5V power output on P3-B pin 9 (EN_OFF_BD_5V)
            subprocess.run(["gpioset", "5", "16=0"])
            self.logger.info(f"Disabled 5V power output for ADC devices")
            return True
        except Exception as e:
            self.logger.exception(f"Error disabling 5V power: {e}")
            return False

    def enable_5v_power(self):
        """Enable the 5V power output for the ADC devices """
        if self.enable_5v_pwr:
            return True
        try:
            # Enable 5V power output on P3-B pin 9 (EN_OFF_BD_5V)
            subprocess.run(["gpioset", "5", "16=1"])
            self.logger.info(f"Enabled 5V power output for ADC devices")
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
        adc_range = ADCRange.RANGE_2_5V if self.adc_max_voltage == 2.5 else ADCRange.RANGE_10_9V
        return self.configure_adc_channel(channel, adc_range)

    def configure_adc_channel(self, channel: ADCChannel, adc_range: ADCRange) -> bool:
        """Configure an ADC channel for the specified range"""
        if self.channels_configured:
            return True
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
                time.sleep(0.01)  # Small delay between readings
                
            return int(total/float(n))
        except Exception as e:
            self.logger.exception(f"Error reading ADC channel {channel_num} via IIO: {e}")
            return None

    def convert_raw_to_voltage(self, raw_value: int) -> float:
        """Convert raw ADC value to voltage"""
        return (raw_value / self.adc_max_raw) * self.adc_max_voltage


    def read_device(self, device: Dict[str, Any]) -> Optional[float]:
        """Read the voltage from the specified device, let sub-class convert to data"""
        if 'channel' not in device:
            self.logger.error(f"Missing channel in device: {device}")
            return None

        channel_num = device['channel']
        raw_value = self.read_raw_adc(channel_num)

        if raw_value is None:
            return None

        voltage = self.convert_raw_to_voltage(raw_value)
        return voltage




    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        """Get identifiers for devices"""
        # Use the MAC address as the identifier
        return {device.get('mac', ''): device.get('mac', '') for device in devices}

    def adc_data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str], hardware_id: str) -> Dict[str, Any]:
        """
        Acquire data from devices

        :param devices: List of devices to read from
        :param scan_group: List of point names to read, not required for ADC measurements
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
            self.channels_configured = True

        for device in devices:
            mac = device.get('mac')
            if not mac:
                self.logger.warning(f"Device missing MAC address: {device}")
                continue

            voltage = self.read_device(device)
            result[mac] = voltage

        if self.disable_pwr_between_reads:
            self.disable_5v_power()
            self.initialized = False

        return result
