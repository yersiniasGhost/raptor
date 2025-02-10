# On the Raptor (Python example)
import requests
from utils.mac_address import get_mac_address


def register_device():
    response = requests.post(
        'https://192.168.1.25:3000/api/v2/raptor/register',
        headers={
            'X-API-Key': 'your-api-key'
        },
        json={
            'mac_address': get_mac_address(),
            'firmware_version': '1.0.0'
        }
    )

    if response.status_code == 200:
        config = response.json()
        # Store MQTT credentials
        save_mqtt_config(config['mqtt'])