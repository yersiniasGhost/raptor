from pathlib import Path
from typing import Tuple
from logging import Logger
from cloud.raptor_commissioner import RaptorCommissioner
from cloud.raptor_configuration import RaptorConfiguration
from database.database_manager import DatabaseManager
from .base_action import Action
from .action_status import ActionStatus
from cloud.telemetry_config import TelemetryConfig
from cloud.mqtt_config import MQTTConfig
from utils import JSON, EnvVars


class RebuildAction(Action):
    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig, logger: Logger) -> Tuple[ActionStatus, JSON]:
        try:

            logger.info("Starting rebuild action.")
            schema_path = Path(EnvVars().schema_path)
            logger.info(f"Updating database with schema: {schema_path}")
            db = DatabaseManager(EnvVars().db_path, schema_path)
            db.rebuild_db(True)
            logger.info("Completed database rebuild")

        except Exception as e:
            logger.error(f"Error during recommission: {e}")
            return ActionStatus.FAILED, {"error": str(e)}

        try:
            logger.info("Recommissioning....")
            rc = RaptorCommissioner()
            if not rc.commission():
                logger.error("Unable to recommission Raptor")
                return ActionStatus.FAILED, {"error": "Unable to recommission Raptor"}
            logger.info("Successfully recommissioned Raptor")
        except Exception as e:
            logger.error(f"Error during recommission: {e}")
            return ActionStatus.FAILED, {"error": str(e)}

        logger.info("Starting recommission action")
        try:
            rc = RaptorConfiguration()
            if not rc.get_configuration():
                logger.error("Unable to recommission Raptor")
                return ActionStatus.FAILED, {"error": "error"}
            logger.info("Successfully recommissioned Raptor")

        except Exception as e:
            logger.error(f"Error during recommission: {e}")
            return ActionStatus.FAILED, {"error": str(e)}

        return ActionStatus.SUCCESS, {"message": "Successfully rebuilt Raptor"}
