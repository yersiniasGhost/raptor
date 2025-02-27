from logging import Logger
from cloud.raptor_configuration import RaptorConfiguration
from .base_action import Action
from .action_status import ActionStatus


class ReconfigureAction(Action):
    async def execute(self, logger: Logger) -> ActionStatus:
        logger.info("Starting recommission action")
        try:
            rc = RaptorConfiguration()
            if not rc.get_configuration():
                logger.error("Unable to recommission Raptor")
                return ActionStatus.FAILED
            logger.info("Successfully recommissioned Raptor")
            return ActionStatus.SUCCESS
        except Exception as e:
            logger.error(f"Error during recommission: {e}")
            return ActionStatus.FAILED
