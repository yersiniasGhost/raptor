import sys
import subprocess
from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from utils import LogManager, JSON, SERVICES



class SystemctlAction(Action):

    async def execute(self, t, m) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("SystemctlAction")
        logger.info("Received systemctl status command")

        try:
            cmd = self.params.get('cmd', "status")
            target = self.params.get('target', 'all')  # 'all' or specific process name
            processes = SERVICES
            if target == 'all':
                targets = processes
            elif target in processes:
                targets = [target]
            else:
                logger.error(f"Invalid target process: {target}")
                return ActionStatus.FAILED, {"error": f"Invalid target process: {target}"}

            results = {}
            for process in targets:
                logger.info(f"Sending systemctl {cmd} to service: {process}")
                try:
                    result = subprocess.run(
                        ['systemctl', cmd, process],
                        check=False,
                        capture_output=True,
                        text=True
                    )
                    output = result.stdout.replace('\\n', '\n')
                    output = str(output)
                    results[process] = {
                        "status": "success",
                        "output": output,
                        "error": result.stderr if result.stderr else None
                    }
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to run {process}: {e}")
                    results[process] = {"status": ActionStatus.FAILED, "output": "", "error": str(e) }
                    return ActionStatus.FAILED, {"results": results}

            return ActionStatus.SUCCESS, {"results": results}

        except Exception as e:
            logger.error(f"Error during restart operation: {e}", exc_info=True)
            return ActionStatus.FAILED, {"error": str(e)}
