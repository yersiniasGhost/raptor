import sys
import subprocess
from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from utils import LogManager, JSON, SERVICES


class RestartAction(Action):

    async def execute(self, t, m) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("RestartAction")
        logger.info("Received restart command, initiating controller restart")
        processes = SERVICES
        try:
            # Get parameters with defaults
            restart_mode = self.params.get('restart_mode', 'service')  # 'service' or 'exit'
            target = self.params.get('target', 'all')  # 'all' or specific process name
            exit_status = self.params.get('exit_status', 42)

            # Determine which processes to restart
            if target == 'all':
                targets = processes
            elif target in processes:
                targets = [target]
            else:
                logger.error(f"Invalid target process: {target}")
                return ActionStatus.FAILED, {"error": f"Invalid target process: {target}"}

            if restart_mode == 'service':
                # Restart systemctl services
                results = {}
                for process in targets:
                    logger.info(f"Restarting service: {process}")
                    try:
                        result = subprocess.run(
                            ['systemctl', 'restart', process],
                            check=True,
                            capture_output=True,
                            text=True
                        )
                        results[process] = "success"
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to restart {process}: {e}")
                        results[process] = f"failed: {str(e)}"

                return ActionStatus.SUCCESS, {"results": results}

            elif restart_mode == 'exit':
                # Exit with special code to trigger restart
                logger.info(f"Exiting with status code {exit_status} to trigger restart")
                if exit_status == 99:
                    logger.info("This will stop the service completely")
                sys.exit(exit_status)

            else:
                logger.error(f"Invalid restart mode: {restart_mode}")
                return ActionStatus.FAILED, {"error": f"Invalid restart mode: {restart_mode}"}

        except Exception as e:
            logger.error(f"Error during restart operation: {e}", exc_info=True)
            return ActionStatus.FAILED, {"error": str(e)}
