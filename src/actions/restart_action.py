import sys
import os
from logging import Logger
from .base_action import Action
from .action_status import ActionStatus


class RestartAction(Action):

    async def execute(self, m, t,  logger: Logger) -> ActionStatus:
        try:
            logger.info("Received restart command, initiating controller restart")
            # Exit with a special code that indicates a requested restart
            # We use 42 as an example, but you can choose any non-zero value
            status = self.params.get('exit_status', 42)
            logger.info(f"If this is 99, the service will stop: {status}")
            sys.exit(status)

        except Exception as e:
            logger.error(f"Error during restart: {e}")
            return ActionStatus.FAILURE, {"error": str(e)}
