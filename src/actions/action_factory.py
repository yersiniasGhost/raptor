# src/actions/action_factory.py
import importlib
from typing import Dict, Any, Tuple
from .action_status import ActionStatus
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from utils import JSON, LogManager


class ActionFactory:

    @staticmethod
    async def execute_action(action_name: str, params: Dict[str, Any],
                             telemetry_config: TelemetryConfig,
                             mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        """Dynamically load and execute an action by name"""
        # Convert action_name to CamelCase and append 'Action'
        logger = LogManager().get_logger("ActionFactory")
        class_name = ''.join(word.capitalize() for word in action_name.split('_')) + 'Action'
        try:

            # Import the module
            module_name = f"actions.{action_name}_action"
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                logger.error(f"Action '{action_name}' not found")
                return ActionStatus.NOT_IMPLEMENTED, None

            # Get the action class
            action_class = getattr(module, class_name)

            # Create and execute the action
            action = action_class(params)
            return await action.execute(telemetry_config, mqtt_config)

        except AttributeError:
            logger.error(f"Action class '{class_name}' not found in module")
            return ActionStatus.NOT_IMPLEMENTED, {"error": f"Action not found: {class_name}"}
        except Exception as e:
            logger.error(f"Error executing action '{action_name}': {e}", exc_info=True)
            return ActionStatus.FAILED, {"error": str(e)}
