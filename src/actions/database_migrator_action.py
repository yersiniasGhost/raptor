from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from utils import JSON, LogManager
from database.database_manager import DatabaseManager


class DatabaseMigratorAction(Action):

    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("DatabaseMigratorAction")
        logger.info(f"Starting Database Migrator: {self.params}")
        try:
            DatabaseManager().run_schema_sql()
            logger.info(f"Successfully applied database migration")
            db_state = DatabaseManager().get_current_firmware_version()
            return ActionStatus.SUCCESS, {"message": f"Migrated database",
                                          "database": db_state}
        except Exception as e:
            logger.error(f"Error during Database migrator: {e}")
            return ActionStatus.FAILED, {"error": str(e)}
