from typing import Tuple
from cloud.raptor_commissioner import RaptorCommissioner
from .base_action import Action
from .action_status import ActionStatus
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from utils import JSON, LogManager


class RecommissionAction(Action):
    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("RecommissionAction")
        logger.info("Starting recommission action")
        try:
            rc = RaptorCommissioner()
            if not rc.commission():
                logger.error("Unable to recommission Raptor")
                return ActionStatus.FAILED, {}
            logger.info("Successfully recommissioned Raptor")
            return ActionStatus.SUCCESS, {}
        except Exception as e:
            logger.error(f"Error during recommission: {e}")
            return ActionStatus.FAILED, {}
