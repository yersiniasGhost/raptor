import json
import aiomqtt
from typing import AsyncGenerator
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from database.database_manager import DatabaseManager
from utils.envvars import EnvVars
from logging import Logger
from utils import JSON


def topic_path(telemetry_config: TelemetryConfig, topic: str) -> str:
    return f"{telemetry_config.root_path}{topic}"


async def publish_payload(mqtt_config: MQTTConfig, topic: str, payload: JSON, logger: Logger):
    try:
        async with aiomqtt.Client(
                hostname=mqtt_config.broker,
                port=mqtt_config.port,
                username=mqtt_config.username,
                password=mqtt_config.password
        ) as client:
            # Publish to telemetry topic
            await client.publish(topic=topic, payload=payload.encode(), qos=1)
        return True
    except Exception as e:
        logger.error(f"Error communicating to MQTT broker: {e}")
        raise


async def upload_telemetry_data_mqtt(mqtt_config: MQTTConfig, telemetry_config: TelemetryConfig, logger: Logger):
    try:
        db = DatabaseManager(EnvVars().db_path)
        payload = db.get_stored_telemetry_data()
        payload = json.dumps(payload)
        return await publish_payload(mqtt_config, telemetry_config.telemetry_topic, payload, logger)
    except Exception as e:
        logger.error(f"Error uploading telemetry data: {e}")
        raise


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
            keepalive=mqtt_config.keepalive,
            identifier=mqtt_config.client_id,
            clean_session=False
        )

        # Connect using the context manager
        async with client as mqtt_client:
            # Subscribe to the topic
            await mqtt_client.subscribe(telemetry_config.messages_topic)
            logger.info(f"MQTT listener established on topic: {telemetry_config.messages_topic}")

            # Yield messages directly
            async for message in mqtt_client.messages:
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


async def upload_command_response(mqtt_config: MQTTConfig,  telemetry_config: TelemetryConfig,
                                  payload: JSON, logger: Logger):
    try:
        payload = json.dumps(payload)
        logger.info(f"Command response: {payload}")
        await publish_payload(mqtt_config, telemetry_config.response_topic, payload, logger)
    except Exception as e:
        logger.error(f"Error uploading telemetry data: {e}")
        raise

