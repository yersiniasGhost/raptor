from logging import Logger
from cloud.raptor_commissioner import RaptorCommissioner
from .base_action import Action
from .action_status import ActionStatus


class RecommissionAction(Action):
    async def execute(self, logger: Logger) -> ActionStatus:
        logger.info("Starting recommission action")
        try:
            rc = RaptorCommissioner()
            if not rc.commission():
                logger.error("Unable to recommission Raptor")
                return ActionStatus.FAILED
            logger.info("Successfully recommissioned Raptor")
            return ActionStatus.SUCCESS
        except Exception as e:
            logger.error(f"Error during recommission: {e}")
            return ActionStatus.FAILED
