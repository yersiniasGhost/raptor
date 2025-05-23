#!/usr/bin/env python3

from typing import Tuple
import subprocess
import time
import os
from datetime import datetime
from utils import LogManager, EnvVars

# Configuration
CHECK_INTERVAL = 300  # Check every 5 minutes (300 seconds)
PING_HOST = "8.8.8.8"  # Google DNS server
PING_COUNT = 3
INTERFACES = {
    "wlan0": {"priority": 1, "is_wireless": True},
    "end0": {"priority": 2, "is_wireless": False, "static_ip": "10.250.250.2/24"},
    "end1": {"priority": 3, "is_wireless": False}
}
REVERSE_TUNNEL_SERVICE = "reverse-tunnel.service"
RETRY_DELAY = 60  # Retry delay in seconds for failed recovery


class NetworkWatchdog:

    def __init__(self):
        self.logger = LogManager("network-watchdog.log").get_logger("NetworkManager")
        self.consecutive_failures = 0
        self.recovery_attempts = 0



    def run_command(self, command) -> Tuple[str, str, int]:
        """Run a shell command and return output and return code"""
        try:
            process = subprocess.Popen(
                command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            return stdout.decode().strip(), stderr.decode().strip(), process.returncode
        except Exception as e:
            self.logger.error(f"Error executing command '{command}': {e}")
            return "", str(e), 1



    def check_wifi(self) -> bool:
        """Check if WiFi interface is up and connected"""
        # Check if interface is UP
        wifi_cmd = "ip link show wlan0"
        wifi_output, wifi_error, wifi_return_code = self.run_command(wifi_cmd)

        if wifi_return_code != 0:
            self.logger.warning("WiFi interface not found or command failed")
            return False

        # Validate that interface state is UP in the output
        if "state UP" not in wifi_output:
            self.logger.warning("WiFi interface is not UP")
            return False

        # Check if connected to an SSID
        ssid_cmd = "wpa_cli -i wlan0 status | grep '^ssid=' | head -1"
        ssid_output, ssid_error, ssid_return_code = self.run_command(ssid_cmd)

        if ssid_return_code != 0 or not ssid_output or ssid_output == "ssid=":
            self.logger.warning("WiFi not connected to any SSID")
            return False

        # Check if we have an IPv4 address
        if not self.has_ipv4_address("wlan0"):
            self.logger.warning("WiFi interface has no IPv4 address")
            return False

        self.logger.info(f"WiFi is connected: {ssid_output}")
        return True



    def check_internet(self) -> bool:
        """Check if we have internet connectivity"""
        cmd = f"ping -c {PING_COUNT} {PING_HOST}"
        self.logger.debug(f"Running: {cmd}")
        stdout, stderr, return_code = self.run_command(cmd)

        # Check return code first
        if return_code != 0:
            self.logger.warning(f"Ping failed with return code {return_code}: {stderr}")
            return False

        # Validate ping output contains expected success indicators
        if f"{PING_COUNT} packets transmitted" not in stdout:
            self.logger.warning("Ping output doesn't show expected packet transmission")
            return False

        # Check for packet loss - should show "0% packet loss" for full success
        if "0% packet loss" in stdout:
            self.logger.debug("Ping successful with no packet loss")
            return True
        elif "packet loss" in stdout:
            self.logger.warning(f"Ping completed but with packet loss: {stdout}")
            # Still consider partial success as internet connectivity
            return True
        else:
            self.logger.warning("Ping output format unexpected")
            return False



    def check_reverse_tunnel(self) -> bool:
        """Check if reverse tunnel is working correctly"""
        # First check if the systemd service is active
        service_cmd = "systemctl is-active reverse-tunnel.service"
        service_output, service_error, service_return_code = self.run_command(service_cmd)

        if service_return_code != 0 or service_output.strip() != "active":
            self.logger.warning(f"Reverse tunnel service is not active. Status: {service_output}")
            return False

        # Check if SSH connection to remote host is established
        # Look for the actual SSH connection (not autossh)
        ssh_cmd = "ss -tpn | grep ':22' | grep ESTAB"
        ssh_output, ssh_error, ssh_return_code = self.run_command(ssh_cmd)

        # Also check if the reverse tunnel ports are being forwarded
        # This checks if something is listening on the forwarded ports locally
        port_cmd = "ss -tln | grep -E ':(2002|2022)'"
        port_output, port_error, port_return_code = self.run_command(port_cmd)

        self.logger.info(f"Reverse tunnel service status: {service_output}")
        self.logger.info(f"SSH connection check: {ssh_output}, return_code: {ssh_return_code}")
        self.logger.info(f"Port forwarding check: {port_output}, return_code: {port_return_code}")

        # Validate SSH connection output
        ssh_connected = (ssh_return_code == 0 and
                         ssh_output and
                         "ESTAB" in ssh_output and
                         "ssh" in ssh_output.lower())

        # Validate port forwarding output
        ports_forwarded = (port_return_code == 0 and
                           port_output and
                           any(port in port_output for port in [":2002", ":2022"]))

        # Service should be active AND either SSH connection or port forwarding should be working
        tunnel_working = ssh_connected or ports_forwarded

        if not tunnel_working:
            self.logger.warning("Neither SSH connection nor port forwarding detected")

        return tunnel_working



    def has_ipv4_address(self, interface) -> bool:
        """Check if interface has an IPv4 address"""
        cmd = f"ip -4 addr show {interface}"
        output, stderr, return_code = self.run_command(cmd)

        if return_code != 0:
            self.logger.warning(f"Failed to check IPv4 address for {interface}: {stderr}")
            return False

        # Validate that output contains an actual inet address (not just the interface)
        if "inet " in output and not output.strip().endswith("scope host"):
            # Make sure it's not just loopback or link-local
            lines = output.split('\n')
            for line in lines:
                if "inet " in line and "scope global" in line:
                    self.logger.debug(f"Found IPv4 address for {interface}: {line.strip()}")
                    return True

        self.logger.debug(f"No valid IPv4 address found for {interface}")
        return False



    def get_active_interfaces(self):
        """Get a list of active network interfaces with their state"""
        results = {}
        for iface in INTERFACES:
            # Check if interface exists and is up
            state_cmd = f"ip link show {iface} 2>/dev/null"
            state_output, state_error, state_rc = self.run_command(state_cmd)

            if state_rc == 0 and state_output:  # Interface exists
                # Parse the actual state from output
                if "state UP" in state_output:
                    state = "UP"
                elif "state DOWN" in state_output:
                    state = "DOWN"
                else:
                    state = "UNKNOWN"

                has_ipv4 = self.has_ipv4_address(iface)

                # For wireless, check if connected to an SSID
                ssid = ""
                if INTERFACES[iface]["is_wireless"]:
                    ssid_cmd = f"wpa_cli -i {iface} status | grep '^ssid=' | head -1 | cut -d= -f2"
                    ssid_output, _, ssid_rc = self.run_command(ssid_cmd)
                    if ssid_rc == 0 and ssid_output:
                        ssid = ssid_output.strip()

                results[iface] = {
                    "state": state,
                    "has_ipv4": has_ipv4,
                    "ssid": ssid if INTERFACES[iface]["is_wireless"] else ""
                }
            else:
                # Interface doesn't exist
                results[iface] = {
                    "state": "NOT_FOUND",
                    "has_ipv4": False,
                    "ssid": ""
                }

        return results



    def restart_wireless(self):
        """Restart wireless connection and ensure IPv4 address"""
        self.logger.info("Restarting wireless connection")

        # Stop wpa_supplicant gracefully if it's running
        self.run_command("wpa_cli -i wlan0 terminate")
        time.sleep(2)

        # Bring interface down and up
        self.run_command("ip link set wlan0 down")
        time.sleep(1)
        self.run_command("ip link set wlan0 up")
        time.sleep(2)

        # Start wpa_supplicant
        self.run_command("wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf")
        time.sleep(5)

        # Check if we're connected to an SSID
        ssid_cmd = "wpa_cli -i wlan0 status | grep '^ssid=' | head -1"
        ssid_output, ssid_error, ssid_rc = self.run_command(ssid_cmd)

        if ssid_rc == 0 and ssid_output and ssid_output != "ssid=":
            ssid = ssid_output.split('=', 1)[1] if '=' in ssid_output else "Unknown"
            self.logger.info(f"Connected to SSID: {ssid}")

            # Release any existing DHCP lease
            self.run_command("dhclient -r wlan0")
            time.sleep(1)

            # Request a new IP address
            dhcp_output, dhcp_stderr, dhcp_rc = self.run_command("dhclient -v wlan0")
            if dhcp_rc != 0:
                self.logger.error(f"DHCP request failed: {dhcp_stderr}")
                return False

            # Verify we got an IPv4 address
            if self.has_ipv4_address("wlan0"):
                self.logger.info("Successfully obtained IPv4 address")
                return True
            else:
                self.logger.error("Failed to obtain IPv4 address")
                return False
        else:
            self.logger.error(f"Failed to connect to any SSID. Output: {ssid_output}")
            return False



    def restart_wired_interfaces(self):
        """Reset wired interfaces to known good state"""
        success = True
        for iface, config in INTERFACES.items():
            if not config["is_wireless"]:
                self.logger.info(f"Resetting wired interface {iface}")

                # Bring interface down
                down_output, down_error, down_rc = self.run_command(f"ip link set {iface} down")
                if down_rc != 0:
                    self.logger.warning(f"Failed to bring {iface} down: {down_error}")
                    success = False
                    continue

                time.sleep(1)

                # Bring interface up
                up_output, up_error, up_rc = self.run_command(f"ip link set {iface} up")
                if up_rc != 0:
                    self.logger.warning(f"Failed to bring {iface} up: {up_error}")
                    success = False
                    continue

                # If it has a static IP configuration, apply it
                if "static_ip" in config:
                    ip_output, ip_error, ip_rc = self.run_command(f"ip addr add {config['static_ip']} dev {iface}")
                    if ip_rc != 0 and "File exists" not in ip_error:
                        self.logger.warning(f"Failed to set static IP on {iface}: {ip_error}")
                        success = False

        return success



    def restart_networking(self):
        """Reset network to a known good state"""
        self.logger.info("Resetting network to known good state")

        # Stop potentially problematic services first
        stop_output, stop_error, stop_rc = self.run_command(f"systemctl stop {REVERSE_TUNNEL_SERVICE}")
        if stop_rc != 0:
            self.logger.warning(f"Failed to stop reverse tunnel service: {stop_error}")

        # Reset wired interfaces
        wired_success = self.restart_wired_interfaces()

        # Restart wireless (most important for internet connectivity)
        wireless_success = self.restart_wireless()

        # Wait for the network to stabilize
        time.sleep(15)

        # Check if we have internet after recovery
        if wireless_success and self.check_internet():
            self.logger.info("Network recovery successful, restarting reverse-tunnel service")
            restart_output, restart_error, restart_rc = self.run_command(f"systemctl restart {REVERSE_TUNNEL_SERVICE}")
            if restart_rc != 0:
                self.logger.warning(f"Failed to restart reverse tunnel service: {restart_error}")
            return True
        else:
            self.logger.warning("Network recovery incomplete, not starting reverse-tunnel yet")
            return False



    def log_network_status(self):
        """Log current network status"""
        interfaces_status, _, _ = self.run_command("ip addr show")
        route_info, _, _ = self.run_command("ip route")
        wpa_status, _, _ = self.run_command("wpa_cli -i wlan0 status 2>/dev/null || echo 'WPA not running'")
        dhcp_leases, _, _ = self.run_command(
            "grep wlan0 /var/lib/dhcp/dhclient.leases 2>/dev/null || echo 'No DHCP leases found'")

        self.logger.info("Current network status:")
        self.logger.info(f"WPA Status:\n{wpa_status}")
        self.logger.info(f"Interfaces:\n{interfaces_status}")
        self.logger.info(f"Routes:\n{route_info}")
        self.logger.info(f"DHCP Leases:\n{dhcp_leases}")

        # Check reverse tunnel status
        tunnel_status, _, _ = self.run_command(f"systemctl status {REVERSE_TUNNEL_SERVICE} | head -3")
        self.logger.info(f"Reverse Tunnel Status:\n{tunnel_status}")



    def run(self):
        """Main watchdog function"""
        self.logger.info("Network watchdog service started")

        while True:
            try:
                # Log current timestamp
                self.logger.info(f"START:  Checking connectivity at {datetime.now()}")

                # Get current status of interfaces
                interfaces_status = self.get_active_interfaces()
                self.logger.info(f"Interface status: {interfaces_status}")

                # Check internet connectivity
                internet_available = self.check_internet()

                if internet_available:
                    self.logger.info("Internet connectivity: OK")

                    # Check reverse tunnel only if internet is available
                    if REVERSE_TUNNEL_SERVICE and not self.check_reverse_tunnel():
                        self.logger.warning("Reverse tunnel not established, restarting service")
                        restart_output, restart_error, restart_rc = self.run_command(
                            f"systemctl restart {REVERSE_TUNNEL_SERVICE}")
                        if restart_rc != 0:
                            self.logger.error(f"Failed to restart reverse tunnel: {restart_error}")

                    self.consecutive_failures = 0
                    self.recovery_attempts = 0
                else:
                    self.consecutive_failures += 1
                    self.logger.warning(f"Internet connectivity: FAILED (Failure #{self.consecutive_failures})")

                    # Log current network status
                    self.log_network_status()

                    # On first failure, just log
                    if self.consecutive_failures == 1:
                        self.logger.info("First failure detected, will check again next cycle")

                    # On second or third consecutive failure, try recovery
                    elif self.consecutive_failures >= 2:
                        self.recovery_attempts += 1
                        self.logger.warning(
                            f"Multiple failures detected, resetting network (attempt #{self.recovery_attempts})")

                        if self.restart_networking():
                            self.logger.info("Network recovery successful")
                            self.consecutive_failures = 0
                            self.recovery_attempts = 0
                        else:
                            self.logger.error("Network recovery failed")
                            # If multiple recovery attempts fail, try waiting longer before next retry
                            if self.recovery_attempts > 2:
                                self.logger.warning(
                                    f"Multiple recovery attempts failed, waiting {RETRY_DELAY * 2}s before next try")
                                time.sleep(RETRY_DELAY)

                # Sleep until next check
                time.sleep(CHECK_INTERVAL)

            except Exception as e:
                self.logger.error(f"Error in watchdog main loop: {e}")
                time.sleep(60)  # Shorter sleep on error


if __name__ == "__main__":
    # Check if running as root
    if os.geteuid() != 0:
        print("This script must be run as root!")
        exit(1)

    nm = NetworkWatchdog()
    nm.run()