from typing import Optional
import psutil
import logging


def get_system_mac() -> Optional[str]:
    """
    Get the MAC address of the first non-loopback network interface.
    Returns:
        str: MAC address if found, None otherwise
    """
    try:
        interfaces = psutil.net_if_addrs()

        # Try ethernet interfaces first
        for interface_name in ['end0', 'eth0', 'en0', 'ens33']:
            if interface_name in interfaces:
                for addr in interfaces[interface_name]:
                    if addr.family == psutil.AF_LINK:
                        return addr.address

        # If no standard ethernet interface found, try any non-loopback interface
        for interface_name, interface_addresses in interfaces.items():
            if interface_name != 'lo':
                for addr in interface_addresses:
                    if addr.family == psutil.AF_LINK:
                        return addr.address

    except Exception as e:
        logging.error(f"Error getting MAC address: {str(e)}")
        return None

    return None
