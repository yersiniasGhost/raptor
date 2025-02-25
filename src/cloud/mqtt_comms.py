import json
import aiomqtt
from typing import List, Any, Dict
import asyncio
from cloud.telemetry_config import TelemetryConfig
from cloud.mqtt_config import MQTTConfig

from logging import Logger


async def upload_telemetry_data_mqtt(mqtt_config: MQTTConfig, telemetry_config: TelemetryConfig,
                                     telemetry_data: Dict[str, Any], logger: Logger):
    try:
        payload = json.dumps(telemetry_data)
        # Connect to the broker
        async with aiomqtt.Client(
                hostname=mqtt_config.broker,
                port=mqtt_config.port,
                username=mqtt_config.username,
                password=mqtt_config.password
        ) as client:
            # Publish to telemetry topic
            await client.publish(topic=telemetry_config.telemetry_path, payload=payload.encode(), qos=1)
        return True

    except Exception as e:
        logger.error(f"Error uploading telemetry data: {e}")
        raise


async def download_incoming_messages_mqtt(mqtt_config: MQTTConfig, telemetry_config: TelemetryConfig,
                                          logger: Logger) -> List[str]:
    """
    Download messages from MQTT broker for a single topic.
    """
    try:
        # Connect to the broker using the context manager
        async with aiomqtt.Client(
                hostname=mqtt_config.broker,
                port=mqtt_config.port,
                username=mqtt_config.username,
                password=mqtt_config.password
        ) as mqtt_client:
            # Subscribe to the single topic
            await mqtt_client.subscribe(telemetry_config.messages_path)
            messages = []
            collection_timeout = 1.0  # seconds to wait for messages

            # Collect messages with timeout
            try:
                messages_iterator = mqtt_client.messages
                async with asyncio.timeout(collection_timeout):
                    async for message in messages_iterator:
                        try:
                            # Decode the payload
                            payload = json.loads(message.payload.decode())
                            messages.append(payload)
                        except json.JSONDecodeError:
                            print(f"Received invalid JSON on topic {message.topic}")
                logger.debug(f"Received {len(messages)} messages from CREM3")
            except asyncio.TimeoutError:
                # This is expected - we're using timeout to limit collection time
                pass
            return messages

    except aiomqtt.MqttError as error:
        logger.error(f"MQTT Error: {error}")
        return []
    except Exception as e:
        logger.error(f"Error downloading MQTT messages: {e}")
        raise
