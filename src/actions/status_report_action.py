from logging import Logger
from .base_action import Action
from .action_status import ActionStatus
from cloud.telemetry_config import TelemetryConfig
from cloud.mqtt_config import MQTTConfig


class StatusReportAction(Action):
    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig, logger: Logger) -> ActionStatus:
        logger.info("Starting Status Report Action")
        return ActionStatus.SUCCESS
