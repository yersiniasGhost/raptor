from typing import Dict
import time
import logging
import threading
from enum import Enum
from multi_relay_controller import MultiRelayController, MultiRelayError
from single_relay_controller import GPIOException
logger = logging.getLogger(__name__)


class AlarmMode(Enum):
    OFF = "off"
    DEFAULT = "default"  # Green light + alarm after delay
    FLASH_RED = "flash_red"  # Flashing red light
    FLASH_ALL = "flash_all"  # All lights flash in sequence
    ALTERNATE = "alternate"  # Red and blue alternate


class BannerAlarmException(Exception):
    pass


class BannerAlarm:
    DELAY_BETWEEN_LIGHTS_AND_ALARM = 2.0  # Seconds
    FLASH_INTERVAL = 1.0

    def __init__(self, configuration: Dict):
        self.active_mode = AlarmMode.OFF
        self.stop_thread = threading.Event()
        self.pattern_thread = None
        relay_config = configuration.get('relays')
        polarity = configuration.get('polarity')

        try:
            self.controller = MultiRelayController(config=relay_config, polarity=polarity)
        except GPIOException:
            raise
        except Exception as e:
            raise BannerAlarmException(f"Unexpected error setting alarm: {str(e)}") from e

    def cleanup(self):
        self.stop_pattern()
        self.controller.cleanup()

    def stop_pattern(self):
        """Stop any running pattern thread"""
        if self.pattern_thread and self.pattern_thread.is_alive():
            self.stop_thread.set()
            self.pattern_thread.join()
            self.stop_thread.clear()
            self.controller.set_all(False)

    def flash_red_pattern(self):
        """Pattern thread for flashing red light"""
        while not self.stop_thread.is_set():
            self.controller.set_relay("red", True)
            time.sleep(self.FLASH_INTERVAL)
            if self.stop_thread.is_set():
                break
            self.controller.set_relay("red", False)
            time.sleep(self.FLASH_INTERVAL)

    def flash_all_pattern(self):
        """Pattern thread for sequencing through all lights"""
        lights = ["red", "blue", "green"]
        current = 0
        while not self.stop_thread.is_set():
            self.controller.set_all(False)
            self.controller.set_relay(lights[current], True)
            current = (current + 1) % len(lights)
            time.sleep(self.FLASH_INTERVAL)

    def alternate_pattern(self):
        """Pattern thread for alternating red and blue"""
        while not self.stop_thread.is_set():
            self.controller.set_relay("red", True)
            self.controller.set_relay("blue", False)
            time.sleep(self.FLASH_INTERVAL)
            if self.stop_thread.is_set():
                break
            self.controller.set_relay("red", False)
            self.controller.set_relay("blue", True)
            time.sleep(self.FLASH_INTERVAL)

    def activate_alarm(self, mode: str) -> Dict[str, str]:
        """
        Turn on the alarm lights and siren as defined by the mode
        Args:
            mode: one of a set of actions we can take with the alarm.
        Returns:
            Dict with status message
        Raises:
        """
        try:
            # Convert string mode to enum
            try:
                alarm_mode = AlarmMode(mode)
            except ValueError:
                raise BannerAlarmException(f"Invalid alarm mode: {mode}")
            self.stop_pattern()

            status = self.controller.get_status_all()
            logger.info(f"Activating alarm with mode: {mode}. Status before: {status}")

            if alarm_mode == AlarmMode.DEFAULT:
                success = self.controller.set_relay("green", True)
                if not success:
                    raise BannerAlarmException(f"Failed to set alarm to mode: {mode}")
                time.sleep(self.DELAY_BETWEEN_LIGHTS_AND_ALARM)
                success = self.controller.set_relay("alarm", True)
                if not success:
                    raise BannerAlarmException(f"Failed to set alarm to mode: {mode}")

            elif alarm_mode == AlarmMode.FLASH_RED:
                self.pattern_thread = threading.Thread(target=self.flash_red_pattern)
                self.pattern_thread.start()

            elif alarm_mode == AlarmMode.FLASH_ALL:
                self.pattern_thread = threading.Thread(target=self.flash_all_pattern)
                self.pattern_thread.start()

            elif alarm_mode == AlarmMode.ALTERNATE:
                self.pattern_thread = threading.Thread(target=self.alternate_pattern)
                self.pattern_thread.start()

            self.active_mode = alarm_mode
            logger.info(f"Status after alarm mode: {alarm_mode}: {self.controller.get_status_all()}")

            return {
                "message": f"Set alarm to mode: {mode}",
                "status": "success"
            }

        except MultiRelayError:  # Re-raise known errors
            raise
        except Exception as e:   # Wrap unknown errors
            raise BannerAlarmException(f"Unexpected error setting alarm: {str(e)}") from e

    def deactivate_alarm(self) -> Dict[str, str]:
        self.stop_pattern()
        status = self.controller.get_status_all()
        logger.info(f"Deactivating alarm. Status before: {status}")
        success = self.controller.set_all(False)
        self.active_mode = AlarmMode.OFF
        return {
            "message": f"Deactivating Alarm",
            "status": success
        }

    def get_status(self) -> Dict[str, any]:
        """Get current alarm status"""
        return {
            "mode": self.active_mode.value,
            "relay_status": self.controller.get_status_all()
        }
