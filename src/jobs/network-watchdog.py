#!/usr/bin/env python3

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



    def run_command(self, command):
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



    def check_internet(self):
        """Check if we have internet connectivity"""
        cmd = f"ping -c {PING_COUNT} {PING_HOST}"
        self.logger.debug(f"Running: {cmd}")
        _, _, return_code = self.run_command(cmd)
        return return_code == 0



    def check_reverse_tunnel(self):
        """Check if reverse tunnel is working correctly"""
        cmd = "ss -tpn | grep autossh | grep ESTAB"
        output, _, return_code = self.run_command(cmd)
        return return_code == 0



    def has_ipv4_address(self, interface):
        """Check if interface has an IPv4 address"""
        cmd = f"ip -4 addr show {interface} | grep -o 'inet [0-9.]*'"
        output, _, return_code = self.run_command(cmd)
        return return_code == 0 and output.startswith("inet ")



    def get_active_interfaces(self):
        """Get a list of active network interfaces with their state"""
        results = {}
        for iface in INTERFACES:
            # Check if interface exists and is up
            state_cmd = f"ip link show {iface} 2>/dev/null | grep -oE 'state (UP|DOWN)' | awk '{{print $2}}'"
            state, _, state_rc = self.run_command(state_cmd)

            if state_rc == 0:  # Interface exists
                has_ipv4 = self.has_ipv4_address(iface)

                # For wireless, check if connected to an SSID
                ssid = ""
                if INTERFACES[iface]["is_wireless"]:
                    ssid_cmd = f"wpa_cli -i {iface} status | grep ssid | grep -v p2p | head -1 | cut -d= -f2"
                    ssid, _, _ = self.run_command(ssid_cmd)

                results[iface] = {
                    "state": state,
                    "has_ipv4": has_ipv4,
                    "ssid": ssid if INTERFACES[iface]["is_wireless"] else ""
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
        ssid_cmd = "wpa_cli -i wlan0 status | grep ssid | grep -v p2p | head -1 | cut -d= -f2"
        ssid, _, ssid_rc = self.run_command(ssid_cmd)

        if ssid_rc == 0 and ssid:
            self.logger.info(f"Connected to SSID: {ssid}")

            # Release any existing DHCP lease
            self.run_command("dhclient -r wlan0")
            time.sleep(1)

            # Request a new IP address
            _, stderr, dhcp_rc = self.run_command("dhclient -v wlan0")
            if dhcp_rc != 0:
                self.logger.error(f"DHCP request failed: {stderr}")
                return False

            # Verify we got an IPv4 address
            if self.has_ipv4_address("wlan0"):
                self.logger.info("Successfully obtained IPv4 address")
                return True
            else:
                self.logger.error("Failed to obtain IPv4 address")
                return False
        else:
            self.logger.error("Failed to connect to any SSID")
            return False



    def restart_wired_interfaces(self):
        """Reset wired interfaces to known good state"""
        for iface, config in INTERFACES.items():
            if not config["is_wireless"]:
                self.logger.info(f"Resetting wired interface {iface}")

                # Bring interface down
                self.run_command(f"ip link set {iface} down")
                time.sleep(1)

                # Bring interface up
                self.run_command(f"ip link set {iface} up")

                # If it has a static IP configuration, apply it
                if "static_ip" in config:
                    self.run_command(f"ip addr add {config['static_ip']} dev {iface}")

        return True



    def restart_networking(self):
        """Reset network to a known good state"""
        self.logger.info("Resetting network to known good state")

        # Stop potentially problematic services first
        self.run_command(f"systemctl stop {REVERSE_TUNNEL_SERVICE}")

        # Reset wired interfaces
        self.restart_wired_interfaces()

        # Restart wireless (most important for internet connectivity)
        wireless_success = self.restart_wireless()

        # Wait for the network to stabilize
        time.sleep(15)

        # Check if we have internet after recovery
        if wireless_success and self.check_internet():
            self.logger.info("Network recovery successful, restarting reverse-tunnel service")
            self.run_command(f"systemctl restart {REVERSE_TUNNEL_SERVICE}")
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
                self.logger.info(f"Checking connectivity at {datetime.now()}")

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
                        self.run_command(f"systemctl restart {REVERSE_TUNNEL_SERVICE}")

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