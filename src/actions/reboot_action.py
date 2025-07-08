import subprocess
import time
import os
from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from utils import LogManager, JSON, SERVICES


class RebootAction(Action):
    """
    Action class for rebooting Linux IIoT edge devices.
    Supports different reboot modes and pre-reboot preparations.
    """



    async def execute(self, t, m) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("RebootAction")
        logger.info("Received reboot command, initiating system reboot")

        try:
            # Get parameters with defaults
            reboot_mode = self.params.get('reboot_mode', 'immediate')  # 'immediate', 'delayed', 'graceful'
            delay_seconds = self.params.get('delay_seconds', 0)  # delay before reboot
            force = self.params.get('force', False)  # force reboot even if processes are running
            graceful_timeout = self.params.get('graceful_timeout', 30)  # timeout for graceful shutdown
            notify_users = self.params.get('notify_users', True)  # notify logged in users
            prepare_services = self.params.get('prepare_services', False)  # prepare services before reboot

            # Validate parameters
            if reboot_mode not in ['immediate', 'delayed', 'graceful']:
                logger.error(f"Invalid reboot mode: {reboot_mode}")
                return ActionStatus.FAILED, {"error": f"Invalid reboot mode: {reboot_mode}"}

            if delay_seconds < 0:
                logger.error("Delay seconds cannot be negative")
                return ActionStatus.FAILED, {"error": "Delay seconds cannot be negative"}

            # Check if we have necessary permissions
            if os.geteuid() != 0:
                logger.error("Reboot action requires root privileges")
                return ActionStatus.FAILED, {"error": "Reboot action requires root privileges"}

            # Pre-reboot preparations
            if prepare_services:
                logger.info("Preparing services for reboot")
                await self._prepare_services(logger)

            # Handle different reboot modes
            if reboot_mode == 'immediate':
                return await self._immediate_reboot(logger, force, notify_users)

            elif reboot_mode == 'delayed':
                return await self._delayed_reboot(logger, delay_seconds, force, notify_users)

            elif reboot_mode == 'graceful':
                return await self._graceful_reboot(logger, graceful_timeout, force, notify_users)

        except Exception as e:
            logger.error(f"Error during reboot operation: {e}", exc_info=True)
            return ActionStatus.FAILED, {"error": str(e)}



    async def _prepare_services(self, logger) -> None:
        """Prepare services for reboot by stopping them gracefully"""
        processes = SERVICES
        processes.pop("cmd-controller")
        logger.info("Stopping services gracefully before reboot")

        for process in processes:
            try:
                # Check if service is active
                result = subprocess.run(
                    ['systemctl', 'is-active', process],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:  # Service is active
                    logger.info(f"Stopping service: {process}")
                    subprocess.run(
                        ['systemctl', 'stop', process],
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    logger.info(f"Successfully stopped service: {process}")
                else:
                    logger.info(f"Service {process} is not active, skipping")

            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to stop service {process}: {e}")
                # Continue with other services



    async def _immediate_reboot(self, logger, force: bool, notify_users: bool) -> Tuple[ActionStatus, JSON]:
        """Perform immediate reboot"""
        logger.info("Initiating immediate reboot")

        try:
            # Notify users if requested
            if notify_users:
                await self._notify_users(logger, "System will reboot immediately")

            # Sync filesystem
            logger.info("Syncing filesystem")
            subprocess.run(['sync'], check=True)

            # Choose reboot command based on force flag
            if force:
                logger.info("Forcing immediate reboot")
                subprocess.run(['systemctl', 'reboot', '--force'], check=True)
            else:
                logger.info("Initiating graceful reboot")
                subprocess.run(['systemctl', 'reboot'], check=True)

            return ActionStatus.SUCCESS, {"message": "Reboot initiated successfully"}

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initiate reboot: {e}")
            return ActionStatus.FAILED, {"error": f"Failed to initiate reboot: {str(e)}"}



    async def _delayed_reboot(self, logger, delay_seconds: int, force: bool, notify_users: bool) -> Tuple[
        ActionStatus, JSON]:
        """Perform delayed reboot"""
        logger.info(f"Scheduling reboot in {delay_seconds} seconds")

        try:
            # Notify users about upcoming reboot
            if notify_users:
                await self._notify_users(logger, f"System will reboot in {delay_seconds} seconds")

            # Schedule reboot using 'shutdown' command
            minutes = max(1, delay_seconds // 60)  # shutdown command uses minutes
            message = f"System reboot scheduled by IIoT controller in {minutes} minute(s)"

            cmd = ['shutdown', '-r', f'+{minutes}', message]

            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Reboot scheduled successfully: {result.stdout}")

            return ActionStatus.SUCCESS, {
                "message": f"Reboot scheduled in {delay_seconds} seconds",
                "scheduled_time": time.time() + delay_seconds
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to schedule reboot: {e}")
            return ActionStatus.FAILED, {"error": f"Failed to schedule reboot: {str(e)}"}



    async def _graceful_reboot(self, logger, timeout: int, force: bool, notify_users: bool) -> Tuple[
        ActionStatus, JSON]:
        """Perform graceful reboot with timeout"""
        logger.info(f"Initiating graceful reboot with {timeout} second timeout")

        try:
            # Notify users about graceful reboot
            if notify_users:
                await self._notify_users(logger, f"System will reboot gracefully in {timeout} seconds")

            # Wait for specified timeout
            if timeout > 0:
                logger.info(f"Waiting {timeout} seconds for graceful shutdown")
                time.sleep(timeout)

            # Sync filesystem
            logger.info("Syncing filesystem")
            subprocess.run(['sync'], check=True)

            # Attempt graceful reboot first
            try:
                logger.info("Attempting graceful reboot")
                subprocess.run(['systemctl', 'reboot'], check=True, timeout=10)

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                if force:
                    logger.warning(f"Graceful reboot failed: {e}. Forcing reboot...")
                    subprocess.run(['systemctl', 'reboot', '--force'], check=True)
                else:
                    raise e

            return ActionStatus.SUCCESS, {"message": "Graceful reboot initiated successfully"}

        except Exception as e:
            logger.error(f"Graceful reboot failed: {e}")
            return ActionStatus.FAILED, {"error": f"Graceful reboot failed: {str(e)}"}



    async def _notify_users(self, logger, message: str) -> None:
        """Notify logged in users about upcoming reboot"""
        try:
            # Send message to all logged in users
            subprocess.run(['wall', message], check=True)
            logger.info(f"Notified users: {message}")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to notify users: {e}")



    async def cancel_reboot(self) -> Tuple[ActionStatus, JSON]:
        """Cancel a scheduled reboot"""
        logger = LogManager().get_logger("RebootAction")
        logger.info("Canceling scheduled reboot")

        try:
            # Cancel scheduled shutdown
            result = subprocess.run(['shutdown', '-c'], check=True, capture_output=True, text=True)
            logger.info(f"Reboot canceled: {result.stdout}")

            return ActionStatus.SUCCESS, {"message": "Scheduled reboot canceled successfully"}

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to cancel reboot: {e}")
            return ActionStatus.FAILED, {"error": f"Failed to cancel reboot: {str(e)}"}
