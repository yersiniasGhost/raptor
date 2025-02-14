import sys
import argparse
from pathlib import Path

from cloud.raptor_commissioner import RaptorCommissioner
from cloud.raptor_configuration import RaptorConfiguration
from cloud.firmware_update import FirmwareUpdater
from database.database_manager import DatabaseManager
from utils import LogManager, EnvVars

logger = LogManager().get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description='Commissioning and configuration manager tool.')
    parser.add_argument('-f', '--force_git', action="store_true",
                        help="Force git to update when current version is None")
    parser.add_argument('-t', '--tag', default="",
                        help="Optional git tag to update the system.")
    parser.add_argument('-c', '--commission', action="store_true",
                        help="Perform commissioning step")
    parser.add_argument('-r', "--rebuild", action="store_true",
                        help="Force the rebuilding of the SQLite databases -- performs wipe")
    parser.add_argument('-n', '--configure', action="store_true",
                        help="Download and refresh the configuration")
    return parser.parse_args()


def main():
    args = parse_args()
    envvars = EnvVars()

    if args.tag:
        firmware = FirmwareUpdater(args.tag, args.force_git)
        firmware.update()

    if args.rebuild:
        schema = Path('/root/raptor/src/database/schema.sql')
        db = DatabaseManager(envvars.db_path, schema)
        db.rebuild_db(True)

    if args.commission:
        # Create and attempt commissioner
        commissioner = RaptorCommissioner()
        if not commissioner.commission():
            logger.error("Failed to commission Raptor")
            sys.exit(1)
        logger.info("Raptor successfully commissioned")

    if args.configure:
        configurator = RaptorConfiguration()
        # Get and save the configuration
        config = configurator.get_configuration()
        if not config:
            logger.error("Failed to get configuration")
            sys.exit(1)
        logger.info("Raptor successfully configured")


if __name__ == "__main__":
    main()
