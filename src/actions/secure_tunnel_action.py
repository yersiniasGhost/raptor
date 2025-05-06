import subprocess
import psutil
from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from utils import LogManager, JSON


class SecureTunnelAction(Action):

    async def execute(self, t, m) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("SecureTunnelAction")
        logger.info("Received secure tunnel command, initiating SSH reverse tunnel")

        try:
            # Get parameters
            action = self.params.get('action', 'start')  # 'start', 'stop', 'status'
            remote_host = self.params.get('remote_host', 'localhost')
            remote_port = self.params.get('remote_port', 80)
            local_port = self.params.get('local_port', 8080)
            ssh_user = self.params.get('ssh_user', 'root')
            ssh_key = self.params.get('ssh_key', '/root/.ssh/CREM3-API-03.pem')

            if action == 'start':
                return await self._start_ssh_tunnel(logger, remote_host, remote_port,
                                                    local_port, ssh_user, ssh_key)
            elif action == 'stop':
                return await self._stop_ssh_tunnel(logger, local_port)
            elif action == 'status':
                status = await self._check_ssh_tunnel(logger, local_port)
                return ActionStatus.SUCCESS, {"status": status}
            else:
                return ActionStatus.FAILED, {"error": f"Invalid action: {action}"}

        except Exception as e:
            logger.error(f"Error during secure tunnel operation: {e}", exc_info=True)
            return ActionStatus.FAILED, {"error": str(e)}


    async def _start_ssh_tunnel(self, logger, remote_host, remote_port, local_port, ssh_user, ssh_key):
        """Start an SSH reverse tunnel"""
        cmd = [
            'ssh', '-N', '-T', '-R', f'{local_port}:localhost:{remote_port}',
            '-i', ssh_key, '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null', '-o', 'ServerAliveInterval=60',
            f'{ssh_user}@{remote_host}'
        ]

        try:
            # Check if tunnel already exists
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'ssh' and cmd[3] in ' '.join(proc.info['cmdline']):
                        logger.info(f"SSH tunnel already running with PID {proc.info['pid']}")
                        return ActionStatus.SUCCESS, {"status": "already_running", "pid": proc.info['pid']}
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

            # Start SSH tunnel in background
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"Started SSH tunnel with PID {process.pid}")
            return ActionStatus.SUCCESS, {"status": "started", "pid": process.pid}

        except Exception as e:
            logger.error(f"Failed to start SSH tunnel: {e}")
            return ActionStatus.FAILED, {"error": str(e)}



    async def _stop_ssh_tunnel(self, logger, local_port):
        """Stop SSH reverse tunnel"""
        killed_pids = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] == 'ssh' and f'-R {local_port}:' in ' '.join(proc.info['cmdline']):
                    proc.terminate()
                    killed_pids.append(proc.info['pid'])
                    logger.info(f"Terminated SSH tunnel with PID {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        if killed_pids:
            return ActionStatus.SUCCESS, {"status": "stopped", "killed_pids": killed_pids}
        else:
            return ActionStatus.SUCCESS, {"status": "not_running"}



    async def _check_ssh_tunnel(self, logger, local_port):
        """Check SSH tunnel status"""
        running_tunnels = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] == 'ssh' and f'-R {local_port}:' in ' '.join(proc.info['cmdline']):
                    running_tunnels.append({"pid": proc.info['pid'], "cmdline": proc.info['cmdline']})
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        return {"running": bool(running_tunnels), "tunnels": running_tunnels}
