from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from utils import LogManager, JSON
from utils import get_git_branches, get_current_branch, COMMON_PATH


class SystemStatusAction(Action):

    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("SystemStatus")
        try:
            current_branch = get_current_branch()
            current_common_branch = get_current_branch(COMMON_PATH)
            results = {
                'Firmware branch': current_branch,
                'Common branch': current_common_branch
            }
            return ActionStatus.SUCCESS, {"results": results}
        except Exception as e:
            logger.error(f"Error during git branch queries: {e}", exc_info=True)
            return ActionStatus.FAILED, {"error": str(e)}
