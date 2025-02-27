from abc import ABC, abstractmethod
from logging import Logger
from .action_status import ActionStatus
from typing import Dict, Any


class Action(ABC):

    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}

    @abstractmethod
    async def execute(self, logger: Logger) -> ActionStatus:
        """Execute the action and return its status"""
        pass
