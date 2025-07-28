#!/usr/bin/env python3

from typing import Tuple
import subprocess
import time
import os
from datetime import datetime
from utils import LogManager
from database.database_manager import DatabaseManager
from hardware.power_5v.power_5v import Power5V

# Configuration
CHECK_INTERVAL = 120  # Check every so often
PING_HOST = "8.8.8.8"  # Google DNS server
PING_COUNT = 3
INTERFACES = {
    "wwan0": {"priority": 1, "is_wireless": True},
    "wlan0": {"priority": 2, "is_wireless": True},
    "end0": {"priority": 3, "is_wireless": False, "static_ip": "10.250.250.2/24"},
    "end1": {"priority": 4, "is_wireless": False}
}
RETRY_DELAY = 60  # Retry delay in seconds for failed recovery


class RaptorWatchdog:

    def __init__(self):
        self.logger = LogManager("raptor-watchdog.log").get_logger("RaptorWatchdog")
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



    def log_network_status(self):
        """Log current network status"""
        interfaces_status, _, _ = self.run_command("ip addr show")
        route_info, _, _ = self.run_command("ip route")
        wpa_status, _, _ = self.run_command("wpa_cli -i wlan0 status 2>/dev/null || echo 'WPA not running'")

        self.logger.info("Current network status:")
        self.logger.info(f"WPA Status:\n{wpa_status}")
        self.logger.info(f"Interfaces:\n{interfaces_status}")
        self.logger.info(f"Routes:\n{route_info}")


    def check_internet_connectivity(self):
        # Get current status of interfaces
        interfaces_status = self.get_active_interfaces()
        self.logger.info(f"Interface status: {interfaces_status}")

        # Check internet connectivity
        internet_available = self.check_internet()

        if internet_available:
            self.logger.info("Internet connectivity: OK")
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

    @staticmethod
    def check_power_5v():
        # NOW Check the Power requests in the database
        Power5V().cleanup_dead_processes()
        Power5V().log_current_power_state()


    def run(self):
        """Main watchdog function"""
        self.logger.info("Network watchdog service started")

        while True:
            try:
                # Log current timestamp
                self.logger.info(f"START:  Checking Raptor state at {datetime.now()}")
                # self.check_internet_connectivity()
                self.check_power_5v()

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

    nm = RaptorWatchdog()
    nm.run()
