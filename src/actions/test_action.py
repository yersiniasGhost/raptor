from logging import Logger
from .base_action import Action
from .action_status import ActionStatus
from cloud.telemetry_config import TelemetryConfig
from cloud.mqtt_config import MQTTConfig


class TestAction(Action):
    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig, logger: Logger) -> ActionStatus:
        respond = self.params.get("respond", "success")
        logger.info(f"Starting Test Action: {respond}")

        if respond == "success":
            return ActionStatus.SUCCESS
        elif respond == "failed":
            return ActionStatus.FAILED
        elif respond == "invalid":
            return ActionStatus.INVALID_PARAMS
        elif respond == "in_progress":
            return ActionStatus.IN_PROGRESS
