# src/actions/action_factory.py
import importlib
from logging import Logger
from typing import Dict, Any
from .action_status import ActionStatus


class ActionFactory:

    @staticmethod
    async def execute_action(action_name: str, params: Dict[str, Any], logger: Logger) -> ActionStatus:
        """Dynamically load and execute an action by name"""
        # Convert action_name to CamelCase and append 'Action'
        class_name = ''.join(word.capitalize() for word in action_name.split('_')) + 'Action'
        try:

            # Import the module
            module_name = f"src.actions.{action_name}_action"
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                logger.error(f"Action '{action_name}' not found")
                return ActionStatus.NOT_IMPLEMENTED

            # Get the action class
            action_class = getattr(module, class_name)

            # Create and execute the action
            action = action_class(params)
            return await action.execute(logger)

        except AttributeError:
            logger.error(f"Action class '{class_name}' not found in module")
            return ActionStatus.NOT_IMPLEMENTED
        except Exception as e:
            logger.error(f"Error executing action '{action_name}': {e}")
            return ActionStatus.FAILED
