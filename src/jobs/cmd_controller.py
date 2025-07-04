import argparse
import asyncio
from typing import Optional
from database.db_utils import get_mqtt_config, get_telemetry_config, get_raptor_configuration
from database.database_manager import DatabaseManager
from utils import LogManager
from config.mqtt_config import MQTTConfig
from cloud.mqtt_comms import setup_mqtt_listener, upload_command_response
from actions.action_factory import ActionFactory
from actions.action_status import ActionStatus
from utils import get_mac_address


class CmdController:

    def __init__(self):
        # Setup logging with rotation and remote logging if needed
        self.logger = LogManager("cmd-controller.log").get_logger("CmdController")
        self.running = True
        self._setup_error_handlers()
        self.mqtt_config: MQTTConfig = get_mqtt_config(self.logger)
        self.raptor_configuration = get_raptor_configuration(self.logger)
        self.telemetry_config = get_telemetry_config(self.logger)
        self.mqtt_task = None



    async def _respond_to_message(self, status: ActionStatus, action_id: str, payload: Optional[dict] = {}):
        payload = payload | {"mac": get_mac_address(), "action_id": action_id, "action_status": status.value}
        self.logger.info(f"Responding to received message with status:{status}, id: {action_id}")

        # The new upload_command_response returns a boolean indicating success
        success = await upload_command_response(self.mqtt_config, self.telemetry_config, payload, self.logger)
        if not success:
            self.logger.warning(f"Failed to send command response for action_id: {action_id}")



    async def _handle_mqtt_messages(self):
        """Task to handle MQTT messages"""
        self.logger.info("Initiating incoming message handler.")

        # The new setup_mqtt_listener handles reconnection internally
        # so we no longer need retry logic here
        while self.running:
            try:
                async for payload in setup_mqtt_listener(self.mqtt_config, self.telemetry_config, self.logger):
                    self.logger.info(f"Received message: {payload}")
                    action_name = payload.get('action')
                    params = payload.get('params', {})
                    action_id = payload.get('action_id', "NA")

                    try:
                        if action_name:
                            status, cmd_response = await ActionFactory.execute_action(action_name, params,
                                                                                      self.telemetry_config,
                                                                                      self.mqtt_config)
                            if status == ActionStatus.NOT_IMPLEMENTED:
                                cmd_response = {"message": f"Action not implemented: {action_name}"}
                                await self._respond_to_message(status, action_id, cmd_response)

                            else:
                                await self._respond_to_message(status, action_id, cmd_response)

                        else:
                            self.logger.error(f"Received message with no action specified")
                            await self._respond_to_message(ActionStatus.INVALID_PARAMS, action_id,
                                                           payload={"message": f"Invalid action: {payload}"})
                    except Exception as e:
                        self.logger.error(f"Error processing MQTT message: {e}", exc_info=True)
                        # Try to notify about the error
                        try:
                            await self._respond_to_message(ActionStatus.ERROR, action_id,
                                                           payload={"message": f"Error processing action: {str(e)}"})
                        except Exception:
                            pass
                        # Continue processing next message
                        continue

            except asyncio.CancelledError:
                self.logger.info("MQTT handling task was cancelled, exiting")
                break
            except Exception as e:
                self.logger.error(f"MQTT connection failed with error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Brief pause before the next iteration
                # The setup_mqtt_listener already implements backoff internally



    async def shutdown(self):
        print("SHUTDOWN")
        self.running = False
        DatabaseManager().close()
        if self.mqtt_task:
            self.mqtt_task.cancel()



    async def main_loop(self):
        """  Main execution loop """
        self.logger.info(f"Starting up Command Controller application.")
        self._start_mqtt_task()
        monitor_task = asyncio.create_task(self._monitor_tasks())

        cnt = 0
        sleep_time = 1
        try:
            while self.running:
                # Keep the main loop running until a shutdown signal is received
                # We just need to wait for tasks to complete or for shutdown
                await asyncio.sleep(sleep_time)
                cnt += 1
                # if cnt > 3600:
                #     cnt = 0
                #     self.logger.info("Hourly heart beat: boomp")

        except Exception as e:
            self.logger.critical(f"Critical error in main loop: {str(e)}", exc_info=True)

        finally:
            monitor_task.cancel()
            if self.mqtt_task:
                self.mqtt_task.cancel()



    def _start_mqtt_task(self):
        """Start MQTT handling task with error recovery"""
        if self.mqtt_task and not self.mqtt_task.done():
            # Cancel existing task if running
            self.mqtt_task.cancel()

        self.mqtt_task = asyncio.create_task(self._handle_mqtt_messages())
        self.mqtt_task.add_done_callback(self._on_handle_mqtt_messages_exit)
        self.logger.info("MQTT task started")



    def _on_handle_mqtt_messages_exit(self, task):
        try:
            # This will raise the exception if the task failed
            result = task.result()
            self.logger.info("MQTT handling task completed normally")
        except asyncio.CancelledError:
            self.logger.info("MQTT handling task was cancelled")
        except Exception as e:
            self.logger.error(f"MQTT handling task failed with exception: {e}")
            # Restart the task if needed
            if self.running:
                asyncio.create_task(self._delayed_mqtt_restart())
                self.logger.warning("MQTT tasks restarted.")



    async def _delayed_mqtt_restart(self):
        """Restart MQTT task with a small delay to prevent rapid cycling"""
        await asyncio.sleep(2)  # 2 second delay
        if self.running:  # Check again after the delay
            self.logger.warning("Restarting MQTT task after failure")
            self._start_mqtt_task()



    async def _monitor_tasks(self):
        """Monitor critical tasks and restart them if they fail"""
        while self.running:
            # Check MQTT task
            if self.mqtt_task and self.mqtt_task.done():
                try:
                    # This will raise any exception that occurred
                    self.mqtt_task.result()
                    self.logger.warning("MQTT task completed unexpectedly")
                except asyncio.CancelledError:
                    # Task was cancelled intentionally, no need to restart
                    pass
                except Exception as e:
                    self.logger.error(f"MQTT task failed with error: {e}")

                # Restart MQTT task if it's not running and should be
                if self.running:
                    self.logger.info("Restarting MQTT task")
                    self._start_mqtt_task()

            # Sleep before checking again
            await asyncio.sleep(10)  # Check every 10 seconds



    def _setup_error_handlers(self):
        """Setup global error handlers"""



        def handle_exception(loop, context):
            exception = context.get('exception')
            message = context.get('message')
            task = context.get('task')

            if exception is None:
                self.logger.critical(f"Unhandled error: {message}")
            else:
                self.logger.critical(f"Unhandled exception in {task}: {str(exception)}", exc_info=exception)

            # If this is a critical task, try to restart the application
            is_critical = False
            if task and hasattr(task, 'get_name'):
                task_name = task.get_name()
                is_critical = any(critical_name in task_name for critical_name in ['main_loop', 'mqtt'])

            if is_critical and self.running:
                self.logger.warning("Critical task failed, attempting recovery")
                # Try to restart specific tasks based on context
                if self.mqtt_task and self.mqtt_task.done():
                    self._start_mqtt_task()



        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)


def parse_args():
    parser = argparse.ArgumentParser(description='Command controller is the listener to the MQTT messages topic. ' \
                                                 'Commands are executed and results sent back to the cloud.')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    controller = CmdController()
    asyncio.run(controller.main_loop())


# Example messages's:
# mosquitto_pub -h localhost -t "raptors/67b672097fc4a4b18476b1ed/messages" -m '{"action":"firmware_update", "params": {"tag":"2025-03-03-lf-influxdb"}}'