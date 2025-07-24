import os
import subprocess
import signal
import time
from typing import Tuple, Optional
from .base_action import Action
from .action_status import ActionStatus
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from utils import JSON, LogManager


class CreateReverseTunnelAction(Action):


    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        self.logger = LogManager().get_logger("ReverseTunnelAction")
        self.pid_file = "/var/run/reverse-tunnel.pid"
        self.ssh_key_path = "/root/.ssh/CREM3-API-03.pem"

        # Extract parameters from self.params
        action = self.params.get("action", "start")  # start, stop, status, restart
        ui_port = self.params.get("ui_port", "2004")
        tunnel_port = self.params.get("tunnel_port", "2024")
        server_user = self.params.get("server_user", "ubuntu")
        server_ip = self.params.get("server_ip", "54.226.49.65")

        self.logger.info(f"Reverse tunnel action: {action}")

        try:
            if action == "start":
                return await self._start_tunnel(ui_port, tunnel_port, server_user, server_ip)
            elif action == "stop":
                return await self._stop_tunnel()
            elif action == "status":
                return await self._get_status()
            elif action == "restart":
                # Stop first, then start
                stop_result = await self._stop_tunnel()
                if stop_result[0] == ActionStatus.SUCCESS or "not running" in stop_result[1].get("message", ""):
                    time.sleep(2)  # Brief pause between stop and start
                    return await self._start_tunnel(ui_port, tunnel_port, server_user, server_ip)
                else:
                    return stop_result
            else:
                return ActionStatus.FAILED, {"error": f"Unknown action: {action}"}

        except Exception as e:
            self.logger.error(f"Error in reverse tunnel action: {e}")
            return ActionStatus.FAILED, {"error": str(e)}



    async def _start_tunnel(self, ui_port: str, tunnel_port: str, server_user: str, server_ip: str) -> Tuple[
        ActionStatus, JSON]:
        self.logger.info(f"Starting reverse tunnel to {server_user}@{server_ip}")

        # Check if already running
        if self._is_tunnel_running():
            return ActionStatus.SUCCESS, {
                "message": "Tunnel is already running",
                "status": "running",
                "pid": self._get_tunnel_pid()
            }

        # Validate network connectivity
        interface = self._get_primary_interface()
        if not interface:
            return ActionStatus.FAILED, {"error": "No internet connectivity available"}

        # Setup routing for the server
        if not self._setup_routing(interface, server_ip):
            self.logger.warning("Failed to setup routing, continuing anyway")

        # Validate SSH key
        if not self._validate_ssh_key():
            return ActionStatus.FAILED, {"error": f"SSH key validation failed: {self.ssh_key_path}"}

        # Build autossh command
        autossh_cmd = [
            "/usr/bin/autossh",
            "-f",  # Fork to background
            "-M", "0",  # Disable monitoring port
            "-o", "ServerAliveInterval 30",
            "-o", "ServerAliveCountMax 3",
            "-o", "ExitOnForwardFailure yes",
            "-o", "StrictHostKeyChecking no",
            "-o", "UserKnownHostsFile /dev/null",
            "-N",  # No remote command
            "-R", f"0.0.0.0:{ui_port}:localhost:8002",
            "-R", f"0.0.0.0:{tunnel_port}:localhost:22",
            "-i", self.ssh_key_path,
            f"{server_user}@{server_ip}"
        ]

        try:
            # Start the tunnel
            self.logger.info(f"Executing: {' '.join(autossh_cmd)}")
            result = subprocess.run(autossh_cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                # Wait a moment for the process to establish
                time.sleep(3)

                # Verify it's actually running
                if self._is_tunnel_running():
                    pid = self._get_tunnel_pid()
                    source_ip = self._get_source_ip(interface)

                    self.logger.info(f"Tunnel started successfully via {interface} (PID: {pid})")
                    return ActionStatus.SUCCESS, {
                        "message": f"Reverse tunnel started successfully via {interface}",
                        "status": "running",
                        "pid": pid,
                        "interface": interface,
                        "source_ip": source_ip,
                        "ui_port": ui_port,
                        "tunnel_port": tunnel_port,
                        "server": f"{server_user}@{server_ip}"
                    }
                else:
                    return ActionStatus.FAILED, {
                        "error": "Tunnel process started but is not running",
                        "stderr": result.stderr
                    }
            else:
                self.logger.error(f"Failed to start tunnel: {result.stderr}")
                return ActionStatus.FAILED, {
                    "error": "Failed to start tunnel",
                    "stderr": result.stderr,
                    "stdout": result.stdout
                }

        except subprocess.TimeoutExpired:
            return ActionStatus.FAILED, {"error": "Tunnel startup timed out"}
        except Exception as e:
            return ActionStatus.FAILED, {"error": f"Failed to start tunnel: {str(e)}"}



    async def _stop_tunnel(self) -> Tuple[ActionStatus, JSON]:
        self.logger.info("Stopping reverse tunnel")

        if not self._is_tunnel_running():
            return ActionStatus.SUCCESS, {
                "message": "Tunnel is not running",
                "status": "stopped"
            }

        try:
            # Get PID before killing
            pid = self._get_tunnel_pid()

            # Kill autossh processes
            subprocess.run(["pkill", "-f", "autossh.*reverse"], capture_output=True)
            subprocess.run(["pkill", "autossh"], capture_output=True)

            # Wait for processes to terminate
            time.sleep(2)

            # Verify it stopped
            if not self._is_tunnel_running():
                # Clean up PID file
                if os.path.exists(self.pid_file):
                    os.remove(self.pid_file)

                self.logger.info("Tunnel stopped successfully")
                return ActionStatus.SUCCESS, {
                    "message": "Reverse tunnel stopped successfully",
                    "status": "stopped",
                    "previous_pid": pid
                }
            else:
                # Force kill if still running
                remaining_pid = self._get_tunnel_pid()
                if remaining_pid:
                    os.kill(int(remaining_pid), signal.SIGKILL)
                    time.sleep(1)

                return ActionStatus.SUCCESS, {
                    "message": "Tunnel forcefully stopped",
                    "status": "stopped"
                }

        except Exception as e:
            self.logger.error(f"Error stopping tunnel: {e}")
            return ActionStatus.FAILED, {"error": f"Failed to stop tunnel: {str(e)}"}



    async def _get_status(self) -> Tuple[ActionStatus, JSON]:
        self.logger.info("Checking reverse tunnel status")

        try:
            is_running = self._is_tunnel_running()
            pid = self._get_tunnel_pid() if is_running else None
            interface = self._get_primary_interface()
            source_ip = self._get_source_ip(interface) if interface else None

            # Get additional process info if running
            process_info = {}
            if is_running and pid:
                try:
                    # Get process details
                    ps_result = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "pid,ppid,etime,cmd", "--no-headers"],
                        capture_output=True, text=True
                    )
                    if ps_result.returncode == 0:
                        process_info["details"] = ps_result.stdout.strip()
                except:
                    pass

            status_data = {
                "status": "running" if is_running else "stopped",
                "pid": pid,
                "interface": interface,
                "source_ip": source_ip,
                **process_info
            }

            return ActionStatus.SUCCESS, status_data

        except Exception as e:
            self.logger.error(f"Error getting tunnel status: {e}")
            return ActionStatus.FAILED, {"error": f"Failed to get status: {str(e)}"}



    def _is_tunnel_running(self) -> bool:
        """Check if the reverse tunnel is currently running"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "autossh.*54.226.49.65"],
                capture_output=True, text=True
            )
            return result.returncode == 0 and result.stdout.strip()
        except:
            return False



    def _get_tunnel_pid(self) -> Optional[str]:
        """Get the PID of the running tunnel process"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "autossh.*54.226.49.65"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        return None



    def _get_primary_interface(self) -> Optional[str]:
        """Get the best available network interface"""
        try:
            # Check cellular first (priority)
            result = subprocess.run(
                ["ip", "route", "show", "dev", "wwan0"],
                capture_output=True, text=True
            )
            if result.returncode == 0 and "default" in result.stdout:
                # Test connectivity
                ping_result = subprocess.run(
                    ["ping", "-c", "1", "-W", "3", "8.8.8.8"],
                    capture_output=True
                )
                if ping_result.returncode == 0:
                    return "wwan0"

            # Fallback to WiFi
            result = subprocess.run(
                ["ip", "route", "show", "dev", "wlan0"],
                capture_output=True, text=True
            )
            if result.returncode == 0 and "default" in result.stdout:
                ping_result = subprocess.run(
                    ["ping", "-c", "1", "-W", "3", "8.8.8.8"],
                    capture_output=True
                )
                if ping_result.returncode == 0:
                    return "wlan0"

        except Exception as e:
            self.logger.error(f"Error getting primary interface: {e}")

        return None



    def _get_source_ip(self, interface: str) -> Optional[str]:
        """Get the IP address of the specified interface"""
        try:
            result = subprocess.run(
                ["ip", "addr", "show", interface],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'inet ' in line and not 'inet 127.' in line:
                        return line.split()[1].split('/')[0]
        except:
            pass
        return None



    def _setup_routing(self, interface: str, remote_host: str) -> bool:
        """Setup routing for the remote host through specified interface"""
        try:
            # Get gateway for interface
            result = subprocess.run(
                ["ip", "route", "show", "dev", interface],
                capture_output=True, text=True
            )

            gateway = None
            for line in result.stdout.split('\n'):
                if 'default' in line:
                    parts = line.split()
                    if 'via' in parts:
                        gateway = parts[parts.index('via') + 1]
                        break

            if gateway:
                # Remove existing route
                subprocess.run(
                    ["ip", "route", "del", remote_host],
                    capture_output=True
                )

                # Add new route
                result = subprocess.run(
                    ["ip", "route", "add", remote_host, "via", gateway, "dev", interface],
                    capture_output=True, text=True
                )

                if result.returncode == 0:
                    self.logger.info(f"Route added: {remote_host} via {gateway} dev {interface}")
                    return True

        except Exception as e:
            self.logger.error(f"Failed to setup routing: {e}")

        return False



    def _validate_ssh_key(self) -> bool:
        """Validate SSH key exists and has correct permissions"""
        try:
            if not os.path.exists(self.ssh_key_path):
                self.logger.error(f"SSH key not found: {self.ssh_key_path}")
                return False

            # Check and fix permissions
            current_perms = oct(os.stat(self.ssh_key_path).st_mode)[-3:]
            if current_perms != "600":
                self.logger.info(f"Fixing SSH key permissions from {current_perms} to 600")
                os.chmod(self.ssh_key_path, 0o600)

            return True

        except Exception as e:
            self.logger.error(f"SSH key validation failed: {e}")
            return False