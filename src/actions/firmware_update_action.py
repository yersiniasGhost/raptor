from typing import Tuple
from cloud.firmware_update import FirmwareUpdater
from .base_action import Action
from .action_status import ActionStatus
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from utils import JSON, LogManager
from database.database_manager import DatabaseManager


class FirmwareUpdateAction(Action):
    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("FirmwareUpdateAction")
        logger.info(f"Starting Firmware Update: {self.params}")
        tag = self.params["tag"]
        try:
            firmware = FirmwareUpdater(tag, False)
            if not firmware.update():
                logger.error("Unable to Update Firmware")
                return ActionStatus.FAILED, {"error": "error"}
            logger.info(f"Successfully updated firmware version to {tag}")
            if self.params['migrate_db']:
                DatabaseManager().run_schema_sql()
                logger.info(f"Successfully applied database migration")
            return ActionStatus.SUCCESS, {"message": f"Updated code to {tag}"}
        except Exception as e:
            logger.error(f"Error during Firmware update: {e}")
            return ActionStatus.FAILED, {"error": str(e)}
