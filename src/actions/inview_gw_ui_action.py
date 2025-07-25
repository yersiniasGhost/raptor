import subprocess
import psutil
from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from utils import LogManager, JSON


# I moved this to reverse-tunnel service
# Use restart action
class InviewGwUi(Action):

    async def execute(self, t, m) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("InviewGWUI Action")
        logger.info(f"Received Inview GW command: {self.params}")

        # We are running this command to expose the Inview GW UI:
        # ssh -o "ServerAliveInterval 30" -o "ServerAliveCountMax 3" -o "ExitOnForwardFailure yes" -N -R 0.0.0.0:2004:10.250.250.1:80
        # -i /root/.ssh/CREM3-API-03.pem ubuntu@54.226.49.65
        try:
            # Get parameters
            action = self.params.get('action', 'start')  # 'start', 'stop'
            remote_host = self.params.get('remote_host', 'localhost')
            remote_port = self.params.get('remote_port', 2002)
            ssh_user = self.params.get('ssh_user', 'ubuntu')
            ssh_key = self.params.get('ssh_key', '/root/.ssh/CREM3-API-03.pem')

            if action == 'start':
                return await self._start_inview_gw(logger, remote_host, remote_port,
                                                   ssh_user, ssh_key)
            elif action == 'stop':
                return await self._stop_inview_gw(logger)
            else:
                return ActionStatus.FAILED, {"error": f"Invalid action: {action}"}

        except Exception as e:
            logger.error(f"Error during secure tunnel operation: {e}", exc_info=True)
            return ActionStatus.FAILED, {"error": str(e)}


    async def _start_inview_gw(self, logger, remote_host, remote_port, ssh_user, ssh_key):
        """Start an SSH reverse tunnel"""
        # ssh -o "ServerAliveInterval 30" -o "ServerAliveCountMax 3"
        # -o "ExitOnForwardFailure yes" -N -R 0.0.0.0:2004:10.250.250.1:80
        # -i /root/.ssh/CREM3-API-03.pem ubuntu@54.226.49.65
        cmd = [
            'ssh', "-o", 'ServerAliveInterval=30', "-o", 'ServerAliveCountMax=3',
            '-o', 'ExitOnForwardFailure=yes', '-N', '-R', f'0.0.0.0:{remote_port}:10.250.250.1:80',
            '-i', ssh_key, f'{ssh_user}@{remote_host}'
        ]

        try:
            # Check if tunnel already exists
            # for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            #     try:
            #         if proc.info['name'] == 'ssh' and cmd[3] in ' '.join(proc.info['cmdline']):
            #             logger.info(f"SSH tunnel already running with PID {proc.info['pid']}")
            #             return ActionStatus.SUCCESS, {"status": "already_running", "pid": proc.info['pid']}
            #     except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            #         pass

            # Start SSH tunnel in background
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"Started Inview GW tunnel with PID {process.pid}")
            return ActionStatus.SUCCESS, {"status": "started", "pid": process.pid}

        except Exception as e:
            logger.error(f"Failed to start Inview GW tunnel: {e}")
            return ActionStatus.FAILED, {"error": str(e)}



    async def _stop_inview_gw(self, logger):
        """Stop SSH reverse tunnel"""
        killed_pids = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] == 'ssh' and f'-R 80:' in ' '.join(proc.info['cmdline']):
                    proc.terminate()
                    killed_pids.append(proc.info['pid'])
                    logger.info(f"Terminated Inview GW with PID {proc.info['pid']}")
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
