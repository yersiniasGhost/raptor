from typing import Optional
import subprocess
import sys
import time
from datetime import datetime
from utils import run_command, kill_screen_session, start_screen_session, EnvVars
from utils import LogManager, EnvVars
from database.database_manager import DatabaseManager


class FirmwareUpdater:

    def __init__(self, target_tag: str, force_update: bool):
        self.logger = LogManager().get_logger("FirmwareUpdater")
        self.repo_path = EnvVars().repository_path
        self.current_version: Optional[str] = None
        self.target_tag: str = target_tag
        self.force_update: bool = force_update
        self.get_current_version()


    def get_current_version(self):
        """Get current git reference."""
        output, success = run_command(['git', 'rev-parse', 'HEAD'])
        if success:
            self.current_version = output
            self.logger.info(f"Current git version is {output}")
        db = DatabaseManager(EnvVars().db_path)
        db_version = db.get_current_firmware_version()
        if db_version:
            self.logger.info(f"Current registered version: {db_version['version_tag']} at {db_version['timestamp']}")
            if db_version['version_tag'] != self.current_version:
                self.logger.warning(f"GIT tag not same as registered version")
        else:
            self.logger.info("No previous Firmware version registered.")


    def backup_current_state(self):
        """Create a backup of the current state."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_ref = f"backup_{timestamp}"
        run_command(['git', 'tag', backup_ref])
        self.logger.info(f"Created backup reference: {backup_ref}")
        return backup_ref


    def update_repository(self, target_ref: str) -> bool:
        """Update the repository to the target reference."""
        self.logger.info(f"Updating to: {target_ref}")

        # Fetch only the target reference
        if target_ref.startswith('v'):  # Tag
            _, fetch_success = run_command(['git', 'fetch', 'origin', f'refs/tags/{target_ref}'], self.logger)
        else:  # Branch
            _, fetch_success = run_command(['git', 'fetch', 'origin', target_ref], self.logger)

        if not fetch_success:
            self.logger.error("Failed to fetch updates")
            return False

        # Create backup
        backup_ref = self.backup_current_state()

        # Try to update to target reference
        if target_ref.startswith('v'):
            _, checkout_success = run_command(['git', 'checkout', target_ref], self.logger)
            if not checkout_success:
                self.logger.error(f"Failed to checkout {target_ref}")
                self.rollback(backup_ref)
                return False

        # Pull latest changes if it's a branch
        else:
            _, branch_success = run_command(['git', 'checkout', '-B', target_ref, '-t',
                                             f'origin/{target_ref}'], self.logger)
            if not branch_success:
                self.logger.error(f"Failed to checkout branch {target_ref}")
                self.rollback(backup_ref)
                return False
            _, pull_success = run_command(['git', 'pull', 'origin', target_ref], self.logger)
            if not pull_success:
                self.logger.error("Failed to pull updates")
                self.rollback(backup_ref)
                return False

        self.target_tag = target_ref
        return True


    def rollback(self, backup_ref: str):
        """Rollback to the backup reference."""
        self.logger.warning(f"Rolling back to {backup_ref}")
        _, success = run_command(['git', 'checkout', backup_ref], self.logger)
        if not success:
            self.logger.error("Failed to rollback! Manual intervention required!")
            sys.exit(1)


    def update(self) -> bool:
        """Main update procedure."""

        if not self.current_version and not self.force_update:
            self.logger.warning("Do not have a current version of repository and no 'force_update'.")
            self.logger.warning("Will not update git without force_update option.")
            return False

        try:
            # Get current version for logging
            self.logger.info(f"Current version: {self.current_version}")

            # Update repository
            if not self.update_repository(self.target_tag):
                return False

            db = DatabaseManager(EnvVars().db_path)
            db.add_firmware_version(self.target_tag)
            self.logger.info("Update completed successfully")
            self.cleanup_repository()
            return True

        except Exception as e:
            self.logger.exception(f"Unexpected error during update: {e}")
            if self.current_version:
                self.rollback(self.current_version)
            return False

    def cleanup_repository(self) -> bool:
        """Clean up unnecessary objects from the repository to free up space."""
        self.logger.info("Starting repository cleanup")

        # Remove loose objects that are no longer referenced
        _, prune_success = run_command(['git', 'prune', '--expire', 'now'])
        if not prune_success:
            self.logger.error("Failed to prune loose objects")
            return False

        # Run garbage collection aggressively
        _, gc_success = run_command([
            'git', 'gc',
            '--aggressive',  # More thorough but slower GC
            '--prune=now',  # Remove all unreachable objects immediately
            '--quiet'  # Reduce output for embedded systems
        ])
        if not gc_success:
            self.logger.error("Failed to run garbage collection")
            return False

        # Calculate space saved (if du command is available)
        try:
            before_size = subprocess.check_output(['du', '-sh', '.git'], cwd=self.repo_path).split()[0]
            after_size = subprocess.check_output(['du', '-sh', '.git'], cwd=self.repo_path).split()[0]
            self.logger.info(f"Repository size changed from {before_size} to {after_size}")
        except subprocess.CalledProcessError:
            self.logger.debug("Could not calculate repository size difference")

        self.logger.info("Repository cleanup completed")
        return True
