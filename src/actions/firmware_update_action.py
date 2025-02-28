from typing import Tuple
from logging import Logger
from cloud.firmware_update import FirmwareUpdater
from .base_action import Action
from .action_status import ActionStatus
from cloud.telemetry_config import TelemetryConfig
from cloud.mqtt_config import MQTTConfig
from utils import JSON, LogManager


class FirmwareUpdateAction(Action):
    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("FirmwareUpdateAction")
        tag = self.params["tag"]
        logger.info(f"Starting Firmware Update: {tag}")
        try:
            firmware = FirmwareUpdater(tag, False)
            if not firmware.update():
                logger.error("Unable to Update Firmware")
                return ActionStatus.FAILED, {"error": "error"}
            logger.info("Successfully recommissioned Raptor")
            return ActionStatus.SUCCESS, {"message": f"Updated code to {tag}"}
        except Exception as e:
            logger.error(f"Error during Firmware update: {e}")
            return ActionStatus.FAILED, {"error": str(e)}
