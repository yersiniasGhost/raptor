from typing import Tuple
from cloud.raptor_configuration import RaptorConfiguration
from .base_action import Action
from .action_status import ActionStatus
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from utils import JSON, LogManager


class ReconfigureAction(Action):

    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("ReconfigureAction")

        logger.info("Starting reconfigure action")
        try:
            rc = RaptorConfiguration()
            if not rc.get_configuration():
                logger.error("Unable to reconfigure Raptor")
                return ActionStatus.FAILED, {"error": "error"}
            logger.info("Successfully reconfigured Raptor")
            return ActionStatus.SUCCESS, {"message": "Reconfigured raptor"}
        except Exception as e:
            logger.error(f"Error during reconfigure: {e}")
            return ActionStatus.FAILED, {"error": str(e)}
