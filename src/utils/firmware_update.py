#!/usr/bin/env python3
import logging
import sys
import time
from datetime import datetime
from utils.linux_utils import run_command, kill_screen_session, start_screen_session


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/firmware_update.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("Updater")


class FirmwareUpdater:

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.current_version = None
        self.target_version = None
        self.screen_sessions = []



    def get_current_version(self) -> str:
        """Get current git reference."""
        output, success = run_command(['git', 'rev-parse', 'HEAD'])
        if success:
            self.current_version = output
            return output
        return None



    def backup_current_state(self):
        """Create a backup of the current state."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_ref = f"backup_{timestamp}"
        run_command(['git', 'tag', backup_ref])
        logging.info(f"Created backup reference: {backup_ref}")
        return backup_ref



    def update_repository(self, target_ref: str) -> bool:
        """Update the repository to the target reference."""
        logging.info(f"Updating to: {target_ref}")

        # Fetch only the target reference
        if target_ref.startswith('v'):  # Tag
            _, fetch_success = run_command(['git', 'fetch', 'origin', f'refs/tags/{target_ref}'], logger)
        else:  # Branch
            _, fetch_success = run_command(['git', 'fetch', 'origin', target_ref], logger)

        if not fetch_success:
            logging.error("Failed to fetch updates")
            return False

        # Create backup
        backup_ref = self.backup_current_state()

        # Try to update to target reference
        if target_ref.startswith('v'):
            _, checkout_success = run_command(['git', 'checkout', target_ref], logger)
            if not checkout_success:
                logging.error(f"Failed to checkout {target_ref}")
                self.rollback(backup_ref)
                return False

        # Pull latest changes if it's a branch
        else:
            _, pull_success = run_command(['git', 'pull', 'origin', target_ref], logger)
            if not pull_success:
                logging.error("Failed to pull updates")
                self.rollback(backup_ref)
                return False

        self.target_version = target_ref
        return True

    @staticmethod
    def rollback(backup_ref: str):
        """Rollback to the backup reference."""
        logging.warning(f"Rolling back to {backup_ref}")
        _, success = run_command(['git', 'checkout', backup_ref], logger)
        if not success:
            logging.error("Failed to rollback! Manual intervention required!")
            sys.exit(1)


    @staticmethod
    def restart_screen_sessions() -> bool:
        """Restart all configured screen sessions."""
        from config.services import sessions
        success = True
        for session in sessions['sessions']:
            name = session['name']
            command = session['command']
            cwd = session['cwd']

            logging.info(f"Restarting screen session: {name}")

            # Kill existing session if it exists
            if not kill_screen_session(name, logger):
                success = False
                continue

            # Start new session
            if not start_screen_session(name, command, cwd, logger):
                success = False
                continue

            # Give it some time to start up
            time.sleep(2)

        return success



    def update(self, target_ref: str) -> bool:
        """Main update procedure."""
        current = self.get_current_version()
        try:
            # Get current version for logging
            logging.info(f"Current version: {current}")

            # Update repository
            if not self.update_repository(target_ref):
                return False

            # Restart screen sessions
            if not self.restart_screen_sessions():
                logging.error("Screen session restart failed, rolling back...")
                self.rollback(current)
                return False

            logging.info("Update completed successfully")
            return True

        except Exception as e:
            logging.exception(f"Unexpected error during update: {e}")
            if current:
                self.rollback(current)
            return False


def main():

    if len(sys.argv) != 2:
        print("Usage: update_firmware.py <target_ref>")
        sys.exit(1)

    target_ref = sys.argv[1]
    updater = FirmwareUpdater("/root/raptor")

    success = updater.update(target_ref)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
