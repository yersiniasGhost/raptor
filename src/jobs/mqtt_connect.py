from typing import AsyncGenerator
from logging import Logger
import aiomqtt
import json
from cloud.mqtt_config import MQTTConfig
from cloud.telemetry_config import TelemetryConfig


async def setup_mqtt_listener(mqtt_config: MQTTConfig,
                              telemetry_config: TelemetryConfig,
                              logger: Logger) -> AsyncGenerator:
    """Set up a persistent MQTT connection and yield messages"""
    try:
        # Create client using context manager
        client = aiomqtt.Client(
            hostname=mqtt_config.broker,
            port=mqtt_config.port,
            username=mqtt_config.username,
            password=mqtt_config.password,
            keepalive=mqtt_config.keepalive
        )

        # Connect using the context manager
        async with client as mqtt_client:
            # Subscribe to the topic
            await mqtt_client.subscribe(telemetry_config.messages_path)
            logger.info(f"MQTT listener established on topic: {telemetry_config.messages_path}")

            # Yield messages directly
            async for message in mqtt_client.messages:
                try:
                    if message.topic.matches(telemetry_config.messages_path):
                        try:
                            payload = json.loads(message.payload.decode())
                            yield payload
                        except json.JSONDecodeError:
                            logger.error(f"Received invalid JSON payload: {message.payload.decode()}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

    except aiomqtt.MqttError as e:
        logger.error(f"MQTT Error: {e}")
    except Exception as e:
        logger.error(f"Failed in MQTT listener: {e}")