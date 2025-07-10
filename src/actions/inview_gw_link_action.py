import subprocess
import signal
import os
from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from utils import LogManager, JSON, get_local_ip


class InviewGwLink(Action):
    """
    Stateless action class for managing SSH tunnel connections.
    Supports connecting and disconnecting SSH reverse tunnels without maintaining state.
    """


    async def execute(self, t, m) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("InviewGwLink")

        try:
            # Get the action type
            action_type = self.params.get('action', 'connect')  # 'connect' or 'disconnect'

            if action_type == 'connect':
                return await self._connect_tunnel(logger)
            elif action_type == 'disconnect':
                return await self._disconnect_tunnel(logger)
            elif action_type == 'status':
                return await self.get_tunnel_status()
            else:
                logger.error(f"Invalid action type: {action_type}")
                return ActionStatus.FAILED, {"error": f"Invalid action type: {action_type}"}

        except Exception as e:
            logger.error(f"Error during SSH tunnel operation: {e}", exc_info=True)
            return ActionStatus.FAILED, {"error": str(e)}



    async def _connect_tunnel(self, logger) -> Tuple[ActionStatus, JSON]:
        """Connect the SSH tunnel"""
        logger.info("Starting SSH tunnel connection")
        port = self.params.get('port')
        aws = self.params.get('aws', False)
        try:
            if aws:
                # SSH command components
                aws_target = self.params.get('aws-target')
                ssh_key = f"/root/.ssh/{self.params.get('ssh-key')}"
                ssh_command = [
                    'ssh',
                    '-o', 'ServerAliveInterval 30',
                    '-o', 'ServerAliveCountMax 3',
                    '-o', 'ExitOnForwardFailure yes',
                    '-N',
                    '-R', f'0.0.0.0:{port}:10.250.250.1:80',
                    '-i', ssh_key,
                    aws_target  # 'ubuntu@54.226.49.65'
                ]
            else:
                local_ip = get_local_ip()
                ssh_command = [
                    'ssh', f'8080:10.250.250.1:80', f'root@{local_ip}'
                ]

            logger.info(f"Executing SSH command: {' '.join(ssh_command)}")

            # Start the SSH tunnel process in background
            process = subprocess.Popen(
                ssh_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent process
            )

            tunnel_pid = process.pid
            logger.info(f"SSH tunnel started with PID: {tunnel_pid}")

            return ActionStatus.SUCCESS, {
                "message": "SSH tunnel connected successfully",
                "pid": tunnel_pid,
                "status": "connected"
            }

        except Exception as e:
            logger.error(f"Failed to connect SSH tunnel: {e}")
            return ActionStatus.FAILED, {"error": f"Failed to connect SSH tunnel: {str(e)}"}



    async def _disconnect_tunnel(self, logger) -> Tuple[ActionStatus, JSON]:
        """Disconnect the SSH tunnel by finding and killing matching processes"""
        logger.info("Disconnecting SSH tunnel")

        try:
            # Find SSH processes matching our specific command
            ps_command = ['ps', 'aux']
            ps_result = subprocess.run(ps_command, capture_output=True, text=True, check=True)

            killed_pids = []
            for line in ps_result.stdout.split('\n'):
                if 'ssh' in line and '10.250.250.1:80' in line:

                    # Extract PID (second column)
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            logger.info(f"Found SSH tunnel process with PID: {pid}")

                            # Try graceful termination first
                            os.kill(pid, signal.SIGTERM)
                            killed_pids.append(pid)

                        except (ValueError, ProcessLookupError) as e:
                            logger.warning(f"Could not kill process {pid}: {e}")

            if killed_pids:
                return ActionStatus.SUCCESS, {
                    "message": f"SSH tunnel(s) disconnected successfully",
                    "killed_pids": killed_pids,
                    "status": "disconnected"
                }
            else:
                return ActionStatus.SUCCESS, {
                    "message": "No SSH tunnel processes found to disconnect",
                    "status": "not_found"
                }

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to find SSH processes: {e}")
            return ActionStatus.FAILED, {"error": f"Failed to find SSH processes: {str(e)}"}
        except Exception as e:
            logger.error(f"Failed to disconnect SSH tunnel: {e}")
            return ActionStatus.FAILED, {"error": f"Failed to disconnect SSH tunnel: {str(e)}"}


    async def get_tunnel_status(self) -> Tuple[ActionStatus, JSON]:
        """Get the current status of SSH tunnels"""
        logger = LogManager().get_logger("SSHTunnelAction")

        try:
            # Check for SSH processes matching our command
            ps_command = ['ps', 'aux']
            ps_result = subprocess.run(ps_command, capture_output=True, text=True, check=True)

            active_tunnels = []
            for line in ps_result.stdout.split('\n'):
                if 'ssh' in line and '10.250.250.1:80' in line:
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            active_tunnels.append({
                                "pid": pid,
                                "command": " ".join(parts[10:])  # Command part
                            })
                        except ValueError:
                            continue

            status = {
                "active_tunnels": len(active_tunnels),
                "tunnels": active_tunnels,
                "status": "connected" if active_tunnels else "disconnected"
            }

            return ActionStatus.SUCCESS, status

        except Exception as e:
            logger.error(f"Error getting tunnel status: {e}")
            return ActionStatus.FAILED, {"error": str(e)}