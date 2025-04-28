from logging import Logger
from typing import List, Optional
import subprocess
from subprocess import CompletedProcess
import time


def local_logger(logger: Optional[Logger] = None):
    if logger is None:
        import logging
        logger = logging.getLogger("linux_utils")
    return logger


def run_command_direct(command: List[str], logger: Optional[Logger] = None) -> Optional[CompletedProcess]:
    """Run a shell command and return output and status."""
    logger = local_logger(logger)
    logger.info(f"Running process: {command}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(command)}")
        logger.error(f"Error output: {e.stderr}")
        return None


# Dumb implementation here:
def run_command(command: List[str], logger: Optional[Logger] = None) -> tuple:
    """Run a shell command and return output and status."""
    logger = local_logger(logger)
    logger.info(f"Running process: {command}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip(), True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(command)}")
        logger.error(f"Error output: {e.stderr}")
        return "Error running command", False


def kill_screen_session(session_name: str, logger: Optional[Logger] = None) -> bool:
    """Kill an existing screen session."""
    logger = local_logger(logger)
    try:
        # Check if session exists
        result = subprocess.run(['screen', '-ls'], capture_output=True, text=True)
        if session_name in result.stdout:
            # Kill the session
            subprocess.run(['screen', '-X', '-S', session_name, 'quit'])
            logger.info(f"Killed screen: {session_name}")
            time.sleep(1)  # Give it time to clean up
        else:
            logger.info(f"No screen session {session_name} to kill")
        return True
    except Exception as e:
        logger.error(f"Failed to kill screen session {session_name}: {e}")
        return False


def start_screen_session(session_name: str, command: str, cwd: Optional[str] = None,
                         logger: Optional[Logger] = None) -> bool:
    """Start a new screen session."""
    logger = local_logger(logger)
    try:
        # Create new detached screen session
        subprocess.run([
            'screen',
            '-dmS',  # Create and detach
            session_name,
            'bash', '-c', command
        ], cwd=cwd, check=True)
        logger.info(f"Started screen session: {session_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to start screen session {session_name}: {e}")
        return False



