import uuid
from typing import Optional
import psutil


def get_mac_address_uuid():
    return ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                     for elements in range(0, 2 * 6, 2)][::-1])


def get_mac_address():
    try:
        with open('/etc/machine-id', 'r') as f:
            return f.read().strip()
    except:
        return None


# Possibly not ever used
def get_system_mac_psutil(logger) -> Optional[str]:
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
        logger.error(f"Error getting MAC address: {str(e)}")
        return None

    return None
