import sys
import logging
import argparse

from cloud.raptor_commissioner import RaptorCommissioner
from cloud.raptor_configuration import RaptorConfiguration
from cloud.firmware_update import FirmwareUpdater
from utils import EnvVars

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('configuration_job')


def parse_args():
    parser = argparse.ArgumentParser(description='Commissioning and configuration manager tool.')
    parser.add_argument('-f', '--force_git', action="store_true",
                        help="Force git to update when current version is None")
    parser.add_argument('-t', '--tag', default="",
                        help="Optional git tag to update the system.")
    parser.add_argument('-c', '--commission', action="store_true",
                        help="Perform commissioning step")
    parser.add_argument('-n', '--configure', action="store_true",
                        help="Download and refresh the configuration")
    return parser.parse_args()


def main():
    args = parse_args()
    api_base_url = EnvVars().api_url

    if args.commission:
        # Create and attempt commissioner
        commissioner = RaptorCommissioner(api_base_url)
        if not commissioner.commission():
            logger.error("Failed to commission Raptor")
            sys.exit(1)
        logger.info("Raptor successfully commissioned")

    if args.configure:
        configurator = RaptorConfiguration(api_base_url)
        # Get and save the configuration
        config = configurator.get_configuration()
        if not config:
            logger.error("Failed to get configuration")
            sys.exit(1)
        logger.info("Raptor successfully configured")

    if args.tag:
        firmware = FirmwareUpdater(args.tag, args.force_git)
        firmware.update()

if __name__ == "__main__":
    main()