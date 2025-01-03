from typing import Dict
import time
import logging
from multi_relay_controller import MultiRelayController, MultiRelayError
from single_relay_controller import GPIOException
logger = logging.getLogger(__name__)


class BannerAlarmException(Exception):
    pass


class BannerAlarm:
    DELAY_BETWEEN_LIGHTS_AND_ALARM = 2  # Seconds

    def __init__(self, configuration: Dict, polarity: str):
        self.polarity = polarity
        try:
            self.controller = MultiRelayController(config=configuration, polarity=polarity)
        except GPIOException:
            raise
        except Exception as e:
            raise BannerAlarmException(f"Unexpected error setting alarm: {str(e)}") from e

    def cleanup(self):
        self.controller.cleanup()


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
            status = self.controller.get_status_all()
            logger.info(f"Activating alarm with mode: {mode}. Status before: {status}")
            if mode:
                success = self.controller.set_relay("green", True)
                if not success:
                    raise BannerAlarmException(f"Failed to set alarm to mode: {mode}")
                time.sleep(self.DELAY_BETWEEN_LIGHTS_AND_ALARM)
                success = self.controller.set_relay("alarm", True)
                if not success:
                    raise BannerAlarmException(f"Failed to set alarm to mode: {mode}")
                logger.info(f"Status after: {self.controller.get_status_all()}")

            return {
                "message": f"Set alarm to mode: {mode}",
                "status": "success"
            }

        except MultiRelayError:  # Re-raise known errors
            raise
        except Exception as e:   # Wrap unknown errors
            raise BannerAlarmException(f"Unexpected error setting alarm: {str(e)}") from e

    def deactivate_alarm(self) -> Dict[str, str]:
        status = self.controller.get_status_all()
        logger.info(f"Deactivating alarm. Status before: {status}")
        success = self.controller.set_all(False)
        return {
            "message": f"Deactivating Alarm",
            "status": success
        }

