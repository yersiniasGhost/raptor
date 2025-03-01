import sys
import subprocess
from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from utils import LogManager, JSON


class SystemctlAction(Action):

    async def execute(self, t, m) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("SystemctlAction")
        logger.info("Received systemctl status command")

        try:
            # Default list of processes
            targets = ["iot-controller", "vmc-ui"]

            results = {}
            for process in targets:
                logger.info(f"Restarting service: {process}")
                try:
                    result = subprocess.run(
                        ['systemctl', 'status', process],
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    results[process] = {
                        "status": "success",
                        "output": result.stdout,
                        "error": result.stderr if result.stderr else None
                    }
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to restart {process}: {e}")
                    results[process] = f"failed: {str(e)}"

            return ActionStatus.SUCCESS, {"results": results}

        except Exception as e:
            logger.error(f"Error during restart operation: {e}", exc_info=True)
            return ActionStatus.FAILED, {"error": str(e)}
