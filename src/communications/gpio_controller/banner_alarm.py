from typing import Dict
import logging
from multi_relay_controller import MultiRelayController, MultiRelayError
from gpio_controller import GPIOException
logger = logging.getLogger(__name__)


class BannerAlarmException(Exception):
    pass


class BannerAlarm:

    def __init__(self, configuration: Dict, polarity: str):
        self.polarity = polarity
        if self.polarity == "high":
            self.on = True
            self.off = False
        else:
            self.on = False
            self.off = True

        try:
            self.controller = MultiRelayController(config=configuration)
        except GPIOException:
            raise
        except Exception as e:
            raise BannerAlarmException(f"Unexpected error setting alarm: {str(e)}") from e

    def cleanup(self):
        self.controller.cleanup(self.polarity)


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
                success = self.controller.set_relay("green", self.on)
                if not success:
                    raise BannerAlarmException(f"Failed to set alarm to mode: {mode}")
                logger.info(f"Status after: {self.controller.get_status_all()}")

            return {
                "message": f"Set alarm to mode: {mode}",
                "status": "success"
            }

        except MultiRelayError:
            # Re-raise known errors
            raise
        except Exception as e:
            # Wrap unknown errors
            raise BannerAlarmException(f"Unexpected error setting alarm: {str(e)}") from e

    def deactivate_alarm(self) -> Dict[str, str]:
        status = self.controller.get_status_all()
        logger.info(f"Deactivating alarm. Status before: {status}")
        success = self.controller.set_all(self.off)
        return success
