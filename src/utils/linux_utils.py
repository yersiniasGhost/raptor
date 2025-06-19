from logging import Logger
from typing import List, Optional, Tuple
import subprocess
from subprocess import CompletedProcess
import time
import re


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


def set_tcp_interface(interface_name: str, expected_ip: str, logger: Optional[Logger]) -> Tuple[bool, dict]:
    cmd = ['ip', 'link', 'set', interface_name, 'down']
    output, status = run_command(cmd, logger)
    if not status:
        logger.error(f"Cannot run ip link set {interface_name} down")
        return check_interface(interface_name, logger)

    cmd = ['ip', 'addr', 'flush', 'dev', interface_name]
    output, status = run_command(cmd, logger)
    if not status:
        logger.error(f"Cannot flush addr on {interface_name}")
        return check_interface(interface_name, logger)

    cmd = ['ip', 'addr', 'add',  f"{expected_ip}", "dev", interface_name]
    output, status = run_command(cmd, logger)
    if not status:
        logger.error(f"Cannot run ip link set {interface_name} down")
        return check_interface(interface_name, logger)

    cmd = ['ip', 'link', 'set', interface_name, 'up']
    output, status = run_command(cmd, logger)
    if not status:
        logger.error(f"Cannot run ip link set {interface_name} up")
        return check_interface(interface_name, logger)

    return check_interface(interface_name, logger)


def check_interface(interface_name: str, logger: Optional[Logger]) -> Tuple[bool, dict]:
    logger = local_logger(logger)
    info = {
        "cmd_success": False,
        'is_up': False,
        'is_running': False,
        'ip_address': None,
        'netmask': None,
        'broadcast': None,
        'mac_address': None,
        'mtu': None
    }
    cmd = ['ifconfig', interface_name]
    output, success = run_command(cmd, logger)
    info['cmd_success'] = success
    if not success:
        return False, info

    # Check interface status flags
    if 'UP' in output:
        info['is_up'] = True
    if 'RUNNING' in output:
        info['is_running'] = True

    # Extract IP information
    inet_pattern = r'inet\s+(\d+\.\d+\.\d+\.\d+)(?:\s+netmask\s+(\d+\.\d+\.\d+\.\d+))?(?:\s+broadcast\s+(\d+\.\d+\.\d+\.\d+))?'
    inet_match = re.search(inet_pattern, output)
    if inet_match:
        info['ip_address'] = inet_match.group(1)
        if inet_match.group(2):
            info['netmask'] = inet_match.group(2)
        if inet_match.group(3):
            info['broadcast'] = inet_match.group(3)

    # Extract MAC address
    mac_pattern = r'ether\s+([0-9a-fA-F:]{17})'
    mac_match = re.search(mac_pattern, output)
    if mac_match:
        info['mac_address'] = mac_match.group(1)

    # Extract MTU
    mtu_pattern = r'mtu\s+(\d+)'
    mtu_match = re.search(mtu_pattern, output)
    if mtu_match:
        info['mtu'] = int(mtu_match.group(1))

    # Add convenience checks
    info['interface_good'] = (
            info['is_up'] and
            info['is_running'] and
            info['ip_address'] is not None
    )

    return True, info


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



