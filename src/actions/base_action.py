from abc import ABC, abstractmethod
from .action_status import ActionStatus
from typing import Dict, Any, Tuple
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from utils import JSON


class Action(ABC):

    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}

    @abstractmethod
    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        """Execute the action and return its status"""
        pass
