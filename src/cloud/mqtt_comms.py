import json
import aiomqtt
import asyncio
import time
from typing import AsyncGenerator, Optional
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from database.database_manager import DatabaseManager
from utils.envvars import EnvVars
from logging import Logger
from utils import JSON


# Track last connection attempt time and backoff parameters
_last_connection_attempt = 0
_connection_failures = 0
_max_backoff_seconds = 300  # Maximum backoff of 5 minutes


def topic_path(telemetry_config: TelemetryConfig, topic: str) -> str:
    return f"{telemetry_config.root_path}{topic}"


def _get_backoff_time() -> float:
    """Calculate exponential backoff time based on connection failures"""
    global _connection_failures
    if _connection_failures == 0:
        return 0

    # Exponential backoff: 2^n seconds, capped at max_backoff_seconds
    backoff = min(2 ** _connection_failures, _max_backoff_seconds)
    return backoff


async def _should_attempt_connection() -> bool:
    """Determine if we should attempt a connection based on backoff strategy"""
    global _last_connection_attempt, _connection_failures

    # If never attempted or no failures, always try
    if _last_connection_attempt == 0 or _connection_failures == 0:
        return True

    # Calculate time since last attempt
    current_time = time.time()
    time_since_last_attempt = current_time - _last_connection_attempt

    # Get required backoff time
    backoff_time = _get_backoff_time()

    # Return True if we've waited long enough
    return time_since_last_attempt >= backoff_time


async def publish_payload(mqtt_config: MQTTConfig, topic: str, payload: JSON, logger: Logger) -> bool:
    """Publish payload to MQTT broker with backoff strategy"""
    global _last_connection_attempt, _connection_failures

    # Check if we should attempt connection based on backoff strategy
    if not await _should_attempt_connection():
        logger.info(f"Skipping MQTT connection attempt due to backoff (waiting for {_get_backoff_time()}s)")
        return False

    # Update last connection attempt time
    _last_connection_attempt = time.time()

    try:
        async with aiomqtt.Client(
                hostname=mqtt_config.broker,
                port=mqtt_config.port,
                username=mqtt_config.username,
                password=mqtt_config.password
        ) as client:
            # Publish to telemetry topic
            await client.publish(topic=topic, payload=payload.encode(), qos=1)

        # Reset connection failures on success
        if _connection_failures > 0:
            logger.info(f"MQTT connection restored after {_connection_failures} failed attempts")
            _connection_failures = 0

        return True
    except Exception as e:
        # Increment connection failures
        _connection_failures += 1
        backoff_time = _get_backoff_time()

        # Log with different levels based on failure count
        if _connection_failures == 1:
            logger.warning(f"Error communicating to MQTT broker: {e}. Will retry in {backoff_time}s")
        elif _connection_failures % 10 == 0:  # Log only every 10 failures to reduce log spam
            logger.error(
                f"Still unable to connect to MQTT broker after {_connection_failures} attempts: {e}. Next retry in {backoff_time}s")

        return False


async def upload_telemetry_data_mqtt(mqtt_config: MQTTConfig, telemetry_config: TelemetryConfig,
                                     logger: Logger) -> bool:
    """Upload telemetry data with backoff strategy"""
    try:
        db = DatabaseManager(EnvVars().db_path)
        payload = db.get_stored_telemetry_data()
        payload = json.dumps(payload)
        return await publish_payload(mqtt_config, telemetry_config.telemetry_topic, payload, logger)
    except Exception as e:
        logger.error(f"Error uploading telemetry data: {e}")
        return False


class MQTTListener:
    """Manages MQTT connection with proper backoff handling"""



    def __init__(self, mqtt_config: MQTTConfig, telemetry_config: TelemetryConfig, logger: Logger):
        self.mqtt_config = mqtt_config
        self.telemetry_config = telemetry_config
        self.logger = logger
        self.client: Optional[aiomqtt.Client] = None
        self.connected = False
        self.connection_failures = 0
        self.last_connection_attempt = 0
        self.max_backoff = 300  # 5 minutes



    async def _get_backoff_time(self) -> float:
        """Calculate exponential backoff time"""
        if self.connection_failures == 0:
            return 0
        # Exponential backoff: 2^n seconds, capped at max_backoff
        return min(2 ** self.connection_failures, self.max_backoff)



    async def connect(self) -> bool:
        """Connect to MQTT broker with backoff strategy"""
        # Check if we should attempt connection based on backoff
        current_time = time.time()
        time_since_last_attempt = current_time - self.last_connection_attempt
        backoff_time = await self._get_backoff_time()

        if self.last_connection_attempt > 0 and time_since_last_attempt < backoff_time:
            self.logger.debug(f"Skipping MQTT connection attempt due to backoff (waiting for {backoff_time}s)")
            return False

        # Update last connection attempt time
        self.last_connection_attempt = current_time

        try:
            # Create client
            self.client = aiomqtt.Client(
                hostname=self.mqtt_config.broker,
                port=self.mqtt_config.port,
                username=self.mqtt_config.username,
                password=self.mqtt_config.password,
                keepalive=self.mqtt_config.keepalive,
                identifier=self.mqtt_config.client_id,
                clean_session=False
            )

            # Connect
            await self.client.connect()

            # Subscribe
            await self.client.subscribe(self.telemetry_config.messages_topic)

            # Reset connection failures
            if self.connection_failures > 0:
                self.logger.info(f"MQTT connection restored after {self.connection_failures} failed attempts")
                self.connection_failures = 0

            self.connected = True
            self.logger.info(f"MQTT listener established on topic: {self.telemetry_config.messages_topic}")
            return True

        except Exception as e:
            # Increment connection failures
            self.connection_failures += 1
            backoff_time = await self._get_backoff_time()

            # Log with different levels based on failure count
            if self.connection_failures == 1:
                self.logger.warning(f"Error connecting to MQTT broker: {e}. Will retry in {backoff_time}s")
            elif self.connection_failures % 10 == 0:  # Log only every 10 failures
                self.logger.error(
                    f"Still unable to connect to MQTT broker after {self.connection_failures} attempts: {e}. Next retry in {backoff_time}s")

            self.connected = False
            return False


async def setup_mqtt_listener(mqtt_config: MQTTConfig,
                              telemetry_config: TelemetryConfig,
                              logger: Logger) -> AsyncGenerator:
    """Set up a persistent MQTT connection with proper backoff and yield messages"""
    listener = MQTTListener(mqtt_config, telemetry_config, logger)
    connection_attempts = 0

    while True:
        if not listener.connected:
            success = await listener.connect()
            if not success:
                # Wait for backoff period
                backoff_time = await listener._get_backoff_time()
                await asyncio.sleep(min(backoff_time, 10))  # Cap sleep at 10s to allow for interruption
                continue

        try:
            # Now that we're connected, yield messages
            async for message in listener.client.messages:
                try:
                    payload = json.loads(message.payload.decode())
                    yield payload
                except json.JSONDecodeError:
                    logger.error(f"Received invalid JSON payload: {message.payload.decode()}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except aiomqtt.MqttError as e:
            logger.warning(f"MQTT connection lost: {e}")
            listener.connected = False
            listener.connection_failures += 1
            await asyncio.sleep(1)  # Brief pause before reconnection attempt

        except Exception as e:
            logger.error(f"Unexpected error in MQTT listener: {e}")
            listener.connected = False
            listener.connection_failures += 1
            await asyncio.sleep(5)  # Longer pause for unexpected errors


async def upload_command_response(mqtt_config: MQTTConfig, telemetry_config: TelemetryConfig,
                                  payload: JSON, logger: Logger) -> bool:
    """Upload command response with backoff strategy"""
    try:
        payload_str = json.dumps(payload)
        logger.info(f"Command response: {payload_str}")
        return await publish_payload(mqtt_config, telemetry_config.response_topic, payload_str, logger)
    except Exception as e:
        logger.error(f"Error uploading command response: {e}")
        return False