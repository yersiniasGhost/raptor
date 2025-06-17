from pathlib import Path
import json
from typing import Dict, Optional, Union, List, Tuple
import threading
import asyncio
import traceback
from concurrent.futures import ThreadPoolExecutor
import canopen
from .electrak import ElectrakMD
from hardware.gpio_controller.banner_alarm import BannerAlarm, BannerAlarmException
from utils import Singleton, run_command, LogManager


class ActuatorManager(metaclass=Singleton):
    """Singleton manager for handling multiple actuators"""

    def __init__(self, channel: str, eds: str):
        """Initialize the manager's resources"""
        self.logger = LogManager().get_logger("ActuatorManager")
        self.actuators: Dict[str, ElectrakMD] = {}
        self.network = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.connection_lock = threading.RLock()  # Using RLock instead of Lock
        self.operation_locks: Dict[str, threading.Lock] = {}
        self.alarm: Optional[BannerAlarm] = None
        self.channel = channel
        self.eds_file = eds
        self.hardware_definition: dict = {}
        self.actuator_defs = {}


    def setup_network(self):
        if self.network is not None:
            self.logger.info("Network is set up already")
            return True
        """Initialize CAN network connection"""
        self.logger.info("Running linux commands to set up network")
        cmd = ['ip', 'link', 'set', 'can0', 'down']
        output, status = run_command(cmd, self.logger)
        cmd = ["ip", "link", "set", "can0", "type", "can", "bitrate", "500000"]
        output, status = run_command(cmd, self.logger)
        self.logger.info(f"ip link set: {status}")
        cmd = ['ip', 'link', 'set', 'can0', 'up']
        output, status = run_command(cmd, self.logger)
        self.logger.info(f"ip link can0 up: {status}")
        cmd = ['ip', 'link', 'show', 'can0']
        output, status = run_command(cmd, self.logger)
        self.logger.info(f"ip link show: {status} / {output}")

        self.logger.info('Setting up network...')
        try:
            self.logger.info('Creating CAN network...')
            self.network = canopen.Network()
            self.logger.info('Connecting to CAN bus...')
            self.network.connect(channel=self.channel, bustype='socketcan')
            self.logger.info('CAN network setup complete')
            return True
        except Exception as e:
            self.logger.error(f'Network setup failed: {e}')
            self.network = None
            return False

    def reset_hardware(self) -> Tuple[str, Union[str, bool]]:
        import traceback
        traceback.print_stack()
        self.logger.info(f"Restarting actuators: {self.network}")
        self.setup_network()
        return self.ping_hardware()

    def ping_hardware(self) -> Tuple[str, Union[str, bool]]:
        result, returnstatus = run_command(["ip", "-details", "link", "show", self.channel], self.logger)
        return result, returnstatus

    def add_actuator(self, actuator_id: str, node_id: int):
        """Add a new actuator to the management system"""
        self.logger.info(f"Adding actuator {actuator_id}, but not initializing it")
        self.actuator_defs[actuator_id] = node_id

    def init_actuators(self):
        try:
            # Setup network first if needed
            if self.network is None:
                if not self.setup_network():
                    self.logger.error("Network setup failed")
                    return False
        except Exception as e:
            self.logger.error(f"Failed to set up canbus network: {e}")
            raise

        for actuator_id, node_id in self.actuator_defs.items():
            # Check if actuator already exists without lock
            if actuator_id in self.actuators:
                self.logger.warning(f"Actuator {actuator_id} already exists")
                continue
            try:

                # Create operation lock for this actuator
                self.operation_locks[actuator_id] = threading.Lock()

                # Create actuator instance
                self.logger.info(f"Creating actuator instance {actuator_id}")
                actuator = ElectrakMD(
                    network=self.network,
                    node_id=node_id,
                    eds_file=self.eds_file,
                    operation_lock=self.operation_locks[actuator_id],
                    executor=self.executor
                )

                # Add to actuators dict with lock
                with self.connection_lock:
                    self.actuators[actuator_id] = actuator

                self.logger.info(f"Successfully added actuator {actuator_id}")

            except Exception as e:
                self.logger.error(f"Failed to add actuator {actuator_id}: {e}")
                print(traceback.format_exc())
                # Cleanup if failure
                if actuator_id in self.operation_locks:
                    del self.operation_locks[actuator_id]
                self.network = None
                return False
        return True

    def get_actuator(self, actuator_id: str) -> Optional[ElectrakMD]:
        """Get actuator instance by ID"""
        if not self.actuators:
            self.init_actuators()
        return self.actuators.get(actuator_id)

    def get_slave_ids(self) -> List[str]:
        return list(self.actuator_defs.keys())


    async def deactivate_warning_alarm(self, banner_alarm: BannerAlarm) -> None:
        """Deactivate warning alarm"""
        try:
            result = banner_alarm.deactivate_alarm()
            if result["status"] != "success":
                raise BannerAlarmException("Failed to deactivate alarm")
        except Exception as e:
            self.logger.error(f"Error deactivating warning alarm: {e}")
            raise BannerAlarmException(f"Failed to deactivate warning alarm: {str(e)}")



    async def activate_warning_alarm(self, banner_alarm: BannerAlarm) -> None:
        """Activate warning alarm and wait for delay"""
        try:
            result = banner_alarm.activate_alarm("default")
            if result["status"] != "success":
                raise BannerAlarmException("Failed to activate alarm")

            # Wait for the warning period
            await asyncio.sleep(banner_alarm.DELAY_BETWEEN_LIGHTS_AND_ALARM)

        except Exception as e:
            self.logger.error(f"Error activating warning alarm: {e}")
            banner_alarm.deactivate_alarm()  # Cleanup on error
            raise BannerAlarmException(f"Failed to activate warning alarm: {str(e)}")



    async def move_one(self, actuator_id, target_position: float, target_speed: float, activate_alarm: bool):
        self.logger.info("Starting single actuator movement")
        if not self.actuators:
            self.init_actuators()
        actuator = self.actuators[actuator_id]
        try:
            if activate_alarm:
                try:
                    await self.activate_warning_alarm()
                except BannerAlarmException as e:
                    self.logger.error(f"Failed to activate alarm {e}")
            success = await actuator.move_to(target_position, target_speed)
            return True
        except Exception as e:
            raise e
        finally:
            if activate_alarm:
                try:
                    await self.deactivate_warning_alarm()
                except BannerAlarmException as e:
                    self.logger.error(f"Failed to Deactivate alarm {e}")


    async def move_multiple(self, target_position: float, target_speed: float):
        """Move multiple actuators simultaneously"""
        self.logger.info("Starting multiple actuator movement")
        if not self.actuators:
            self.init_actuators()
        try:
           
            # Create movement tasks
            tasks = []
            for act_id, actuator in self.actuators.items():
                tasks.append(actuator.move_to(target_position, target_speed))
           
            # Execute all movements concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check results
            success = all(isinstance(r, bool) and r for r in results)
            return success
            
        except Exception as e:
            self.logger.error(f"Multi-actuator movement error: {e}")
            return False


    async def cleanup(self):
        """Cleanup all resources"""
        self.logger.info("Starting cleanup")
        try:
            # Stop all actuators
            for actuator in list(self.actuators.values()):
                try:
                    actuator.close()
                except Exception as e:
                    self.logger.error(f"Error cleaning up actuator: {e}")
            
            # Disconnect network
            if self.network:
                try:
                    self.network.disconnect()
                except Exception as e:
                    self.logger.error(f"Error disconnecting network: {e}")
            
            # Shutdown thread pool
            try:
                self.executor.shutdown(wait=False)
            except Exception as e:
                self.logger.error(f"Error shutting down executor: {e}")
            
        finally:
            self.network = None
            self.actuators.clear()
            self.operation_locks.clear()
            self.logger.info("Cleanup complete")


    @classmethod
    def from_dict(cls, actuator_map: dict, logger) -> 'ActuatorManager':
        ActuatorManager.delete_instance()
        try:
            logger.info(actuator_map)
            # hardware = actuator_map['Actuators']
            parameters = actuator_map['parameters']
            devices = actuator_map['devices']
        except KeyError as e:
            logger.error(f"Missing required configuration field: {e}")
            raise
        try:
            manager = cls(parameters['channel'], parameters['eds'])
            manager.hardware_definition = actuator_map
            for device in devices:
                manager.add_actuator(device['mac'], device['node_id'])
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid actuators configuration: {e}")
            raise ValueError(f"Failed to create ActuatorManager: {e}")
        return manager


    @classmethod
    def from_json(cls, json_file: Union[Path, str], logger) -> "ActuatorManager":
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"Failed to read file {json_file}: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_file}: {str(e)}")
            raise
        logger.debug(f"Loaded JSON file:{json_file} \nDATA\n{data}")
        return cls.from_dict(data, logger)
