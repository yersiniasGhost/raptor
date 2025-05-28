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


async def setup_mqtt_listener(mqtt_config: MQTTConfig,
                              telemetry_config: TelemetryConfig,
                              logger: Logger) -> AsyncGenerator:
    """Set up a persistent MQTT connection with proper backoff and yield messages"""
    # Track connection attempts for backoff
    connection_failures = 0
    last_connection_attempt = 0
    max_backoff = 300  # 5 minutes max backoff

    while True:
        current_time = time.time()

        # Calculate backoff time based on failures
        backoff_time = 0
        if connection_failures > 0:
            backoff_time = min(2 ** connection_failures, max_backoff)

        # Determine if we should attempt connection based on backoff
        time_since_last_attempt = current_time - last_connection_attempt
        if last_connection_attempt > 0 and time_since_last_attempt < backoff_time:
            wait_time = min(backoff_time - time_since_last_attempt, 10)  # Cap at 10s for responsiveness
            logger.debug(f"Waiting for backoff: {wait_time:.1f}s before next connection attempt")
            await asyncio.sleep(wait_time)
            continue

        # Update last attempt time
        last_connection_attempt = current_time

        try:
            # Use context manager for MQTT client connection
            async with aiomqtt.Client(
                    hostname=mqtt_config.broker,
                    port=mqtt_config.port,
                    username=mqtt_config.username,
                    password=mqtt_config.password,
                    keepalive=mqtt_config.keepalive,
                    identifier=mqtt_config.client_id,
                    clean_session=False
            ) as client:
                # Subscribe to the messages topic
                await client.subscribe(telemetry_config.messages_topic)

                # Log successful connection (with reconnection info if applicable)
                if connection_failures > 0:
                    logger.info(f"MQTT connection restored after {connection_failures} failed attempts")
                    connection_failures = 0
                else:
                    logger.info(f"MQTT listener established on topic: {telemetry_config.messages_topic}")

                # Process messages as they arrive
                async for message in client.messages:
                    try:
                        payload = json.loads(message.payload.decode())
                        yield payload
                    except json.JSONDecodeError:
                        logger.error(f"Received invalid JSON payload: {message.payload.decode()}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

        except aiomqtt.MqttError as e:
            # Increment connection failures for backoff calculation
            connection_failures += 1
            backoff_time = min(2 ** connection_failures, max_backoff)

            # Log with different verbosity levels based on failure count
            if connection_failures < 10:
                logger.warning(f"MQTT connection error: {e}. Will retry in {backoff_time}s")
            elif connection_failures % 10 == 0:  # Log less frequently after multiple failures
                logger.error(
                    f"Still unable to connect to MQTT broker after {connection_failures} attempts: {e}. Next retry in {backoff_time}s")

            # Brief pause before next iteration
            await asyncio.sleep(1)

        except Exception as e:
            # Handle any other exceptions with backoff
            connection_failures += 1
            backoff_time = min(2 ** connection_failures, max_backoff)

            logger.error(f"Unexpected error in MQTT listener: {e}")
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


async def check_connection(mqtt_config: MQTTConfig, logger: Logger) -> bool:
    """Check MQTT connection status by attempting a quick connection test"""
    try:
        # Quick connection test with short timeout
        async with aiomqtt.Client(
                hostname=mqtt_config.broker,
                port=mqtt_config.port,
                username=mqtt_config.username,
                password=mqtt_config.password,
                timeout=5.0,  # 5 second timeout for quick check
                keepalive=10
        ) as client:
            # Simple ping test - subscribe to a test topic briefly
            await client.subscribe("$SYS/broker/uptime")  # Standard MQTT broker topic
            logger.info("Successfully connected and ping'd.")
            return True
    except  asyncio.TimeoutError:
        logger.warning(f"MQTT connection test timed out after 5 seconds")
        return False
    except ConnectionRefusedError:
        logger.warning(f"MQTT connection refused - check broker address and port")
        return False
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"MQTT connection check failed: {error_msg}")
        return False
