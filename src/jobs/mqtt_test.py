# Notes:
#  ip addr add 10.250.250.2/24 dev end0
from datetime import datetime
import time
import paho.mqtt.client as mqtt
import json

from database.hardware import load_hardware_from_json_file
from hardware.hardware_deployment import BatteryDeployment
from hardware.modbus.modbus import modbus_data_acquisition_orig
from hardware.modbus.modbus_map import ModbusMap
from utils.system_status import collect_system_stats

DATA_PATH = "/root/raptor/data/"


# Callback when the client receives a CONNACK response from the server
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    print(userdata)
    print(flags)
    print('-----------')


# Callback when a message is received from the server
def on_message(client, userdata, msg):
    print(f"Received message on {msg.topic}: {msg.payload.decode()}")
    print(userdata)
    # Handle any commands from the server here


def send_to_crem3(macaddr: str, data: dict):
    print("sending to CREM3")
    topic = f"devices/{macaddr}/readings"
    print(topic)
    client.publish(topic, json.dumps(data))


if __name__ == "__main__":

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.username_pw_set("frich", "2kdZ*97")
    client.connect("192.168.1.25", 1883, 60)
    client.loop_start()

    modbus_map = ModbusMap.from_json("../../data/Sierra25/modbus_map_basic.json")
    inview = load_hardware_from_json_file("../../data/Sierra25/converter_deployment.json")

    batteries = BatteryDeployment.from_json(f"{DATA_PATH}/Esslix/battery_deployment.json")
    register_map = ModbusMap.from_json(f"{DATA_PATH}/Esslix/modbus_map.json")
    cnt = 0

    while(cnt < 1000000000):
        # Get data from each slave
        values = modbus_data_acquisition_orig(inview, modbus_map, slave_id=1)
        if values:
            send_to_crem3("inverter", values)
        for battery in batteries.each_unit():
            values = modbus_data_acquisition_orig(batteries.hardware, register_map, slave_id=battery.slave_id)
            if values:
                send_to_crem3(f"battery{battery.slave_id}", values)

        sbc_state = collect_system_stats()

        print(f"Data sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("---------")
        cnt += 1
        time.sleep(29)
