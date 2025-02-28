from .base_action import Action
from .action_status import ActionStatus
from cloud.telemetry_config import TelemetryConfig
from cloud.mqtt_config import MQTTConfig
from utils import JSON, LogManager
from typing import Tuple


class TestAction(Action):

    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("RebuildAction")

        respond = self.params.get("respond", "success")
        logger.info(f"Starting Test Action: {respond}")

        if respond == "success":
            return ActionStatus.SUCCESS, {"response": "success"}
        elif respond == "failed":
            return ActionStatus.FAILED, {"response": "failed"}
        elif respond == "invalid":
            return ActionStatus.INVALID_PARAMS, {"response": "invalid"}
        elif respond == "in_progress":
            return ActionStatus.IN_PROGRESS, {"response": "in_progress"}
        elif respond == "no_response":
            return ActionStatus.NO_RESPONSE, None
        else:
            return ActionStatus.INVALID_PARAMS, {"error": "Come on man!"}
