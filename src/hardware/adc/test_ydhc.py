import json
import time
from hardware.adc.ct_hall import ADCHardware

from utils import LogManager


def load_config(config_path):
    """Load configuration from JSON file"""
    with open(config_path, 'r') as f:
        return json.load(f)


def main():
    logger = LogManager("./test.log").get_logger("main")
    logger.info("RUNNING")
    # Load configuration
    config = load_config("ct_config4.json")

    # Initialize CT hardware
    ct_hardware = ADCHardware.from_config(config)

    # Get devices from config
    devices = config.get('devices', [])

    # Test all devices
    print("Testing CT devices:")
    for device in devices:
        test_result = ct_hardware.test_device(device)
        print(f"  Device: {device.get('name', device.get('mac', 'unknown'))}")
        print(f"    Status: {test_result['status']}")
        print(f"    Raw ADC: {test_result['raw']}")
        print(f"    Voltage: {test_result['voltage']:.3f} V")
        print(f"    Current: {test_result['current']:.3f} A")
        print(f"    Power: {test_result['current'] * 91.0:.3f} W")
        if test_result['error']:
            print(f"    Error: {test_result['error']}")
        print()

    # Example of continuous monitoring
    print("Starting continuous monitoring (Ctrl+C to stop):")
    try:
        while False:
            for device in devices:
                current = ct_hardware.read_device_current(device)
                name = device.get('name', device.get('mac', 'unknown'))
                if current is not None:
                    print(f"{name}: {current:.3f} A", end="  ")
            for device in devices:
                test_result = ct_hardware.test_device(device)
                print(f"  Device: {device.get('name', device.get('mac', 'unknown'))}")
                print(f"    Status: {test_result['status']}")
                print(f"    Raw ADC: {test_result['raw']}")
                print(f"    Voltage: {test_result['voltage']:.3f} V")
                print(f"    Current: {test_result['current']:.3f} A")
                if test_result['error']:
                    print(f"    Error: {test_result['error']}")
                print()

            print()
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nMonitoring stopped")

    # Example of using data_acquisition
    print("\nDemonstrating data_acquisition method:")
    # Use all point names for scan group
    scan_group = [device.get('name', device.get('mac', 'unknown')) for device in devices]
    hardware_id = "ct_hardware_1"

    # results = ct_hardware.data_acquisition(devices, [], hardware_id)
    # print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()