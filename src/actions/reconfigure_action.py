from typing import Tuple
from cloud.raptor_configuration import RaptorConfiguration
from .base_action import Action
from .action_status import ActionStatus
from cloud.telemetry_config import TelemetryConfig
from cloud.mqtt_config import MQTTConfig
from utils import JSON, LogManager


class ReconfigureAction(Action):

    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("ReconfigureAction")

        logger.info("Starting recommission action")
        try:
            rc = RaptorConfiguration()
            if not rc.get_configuration():
                logger.error("Unable to recommission Raptor")
                return ActionStatus.FAILED, {"error": "error"}
            logger.info("Successfully recommissioned Raptor")
            return ActionStatus.SUCCESS, None
        except Exception as e:
            logger.error(f"Error during recommission: {e}")
            return ActionStatus.FAILED, {"error": str(e)}
