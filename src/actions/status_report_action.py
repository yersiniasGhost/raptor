from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from utils import LogManager, JSON


class StatusReportAction(Action):

    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("RebuildAction")

        logger.info("Starting Status Report Action")
        return ActionStatus.SUCCESS, {"message": "duh"}
