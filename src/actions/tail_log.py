import os
import subprocess
from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from utils import LogManager, JSON
from utils import EnvVars


class TailLogAction(Action):

    async def execute(self, t, m) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("TailLogAction")
        logger.info(f"Received tail log command: {self.params}")

        try:
            log_file = self.params.get('process', None)
            lines = self.params.get('lines', 10)  # Default to last 10 lines
            if not log_file:
                logger.error("No log file specified")
                return ActionStatus.FAILED, {"error": "No log file specified"}

            log_path = EnvVars().log_path + "/" + log_file
            if not os.path.exists(log_path):
                logger.error(f"Log file not found: {log_path}")
                return ActionStatus.FAILED, {"error": f"Log file not found: {log_file}"}

            logger.info(f"Tailing {lines} lines from {log_file}")
            try:
                result = subprocess.run(
                    ['tail', f'-n{lines}', log_path],
                    check=False,
                    capture_output=True,
                    text=True
                )
                output = result.stdout.replace('\\n', '\n')
                output = str(output)

                return ActionStatus.SUCCESS, {
                    "results": {
                        "status": "success",
                        "output": output,
                        "error": result.stderr if result.stderr else None
                    }
                }
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to tail log file {log_file}: {e}")
                return ActionStatus.FAILED, {
                    "results": {
                        "file": log_file,
                        "lines": lines,
                        "status": "failed",
                        "output": "",
                        "error": str(e)
                    }
                }

        except Exception as e:
            logger.error(f"Error during tail log operation: {e}", exc_info=True)
            return ActionStatus.FAILED, {"error": str(e)}