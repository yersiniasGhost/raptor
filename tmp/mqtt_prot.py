import asyncio
import aiomqtt
import sys


async def test_mqtt_connection(host="localhost", port=1883, username=None, password=None):
    print(f"Testing connection to MQTT broker at {host}:{port}")

    try:
        # Set up connection parameters
        connection_params = {
            "hostname": host,
            "port": port,
        }

        # Add authentication if provided
        if username and password:
            connection_params["username"] = username
            connection_params["password"] = password
            print(f"Using authentication with username: {username}")

        # Connect to the broker
        async with aiomqtt.Client(**connection_params) as client:
            print("✅ Successfully connected to MQTT broker!")

            # Subscribe to a test topic
            await client.subscribe("test/connection")
            print("✅ Successfully subscribed to 'test/connection' topic")

            # Publish a test message
            await client.publish("test/connection", payload="Hello MQTT!")
            print("✅ Successfully published test message")

            # Wait briefly to collect messages
            print("Waiting for messages for 3 seconds...")
            try:
                # Get the messages iterator object first, then iterate through it
                messages_iterator = client.messages  # No parentheses here
                async with asyncio.timeout(3):
                    async for message in messages_iterator:
                        print(f"Received message on topic '{message.topic}': {message.payload.decode()}")
            except asyncio.TimeoutError:
                print("Timeout reached, no more messages.")

            print("✅ Test completed successfully")

    except aiomqtt.MqttError as e:
        print(f"❌ Failed to connect: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    # Get connection parameters from command line args
    host = "localhost"
    port = 1883
    username = None
    password = None

    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    if len(sys.argv) > 3:
        username = sys.argv[3]
    if len(sys.argv) > 4:
        password = sys.argv[4]

    # Run the connection test
    asyncio.run(test_mqtt_connection(host, port, username, password))