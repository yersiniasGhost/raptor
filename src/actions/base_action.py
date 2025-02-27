from abc import ABC, abstractmethod
from logging import Logger
from .action_status import ActionStatus
from typing import Dict, Any, Tuple
from cloud.telemetry_config import TelemetryConfig
from cloud.mqtt_config import MQTTConfig
from utils import JSON


class Action(ABC):

    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}

    @abstractmethod
    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig, logger: Logger) -> Tuple[ActionStatus, JSON]:
        """Execute the action and return its status"""
        pass
