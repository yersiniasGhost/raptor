from pathlib import Path
import json
from typing import Dict, Optional, Union
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
import canopen
from .electrak import ElectrakMD
from communications.gpio_controller.banner_alarm import BannerAlarm
from utils import Singleton
import logging
import traceback
logger = logging.getLogger(__name__)


class ActuatorManager(metaclass=Singleton):
    """Singleton manager for handling multiple actuators"""

    def __init__(self, channel: str, eds: str):
        """Initialize the manager's resources"""
        self.actuators: Dict[int, ElectrakMD] = {}
        self.network = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.connection_lock = threading.RLock()  # Using RLock instead of Lock
        self.operation_locks: Dict[int, threading.Lock] = {}
        self.alarm = BannerAlarm
        self.channel = channel
        self.eds_file = eds

    def setup_network(self):
        """Initialize CAN network connection"""
        logger.info('Setting up network...')
        try:
            if self.network is None:
                logger.info('Creating CAN network...')
                self.network = canopen.Network()
                logger.info('Connecting to CAN bus...')
                self.network.connect(channel=self.channel, bustype='socketcan')
                logger.info('CAN network setup complete')
            return True
        except Exception as e:
            logger.error(f'Network setup failed: {e}')
            self.network = None
            return False
                
    def add_actuator(self, actuator_id: int, node_id: int):
        """Add a new actuator to the management system"""
        logger.info(f"Adding actuator {actuator_id}")

        # Check if actuator already exists without lock
        if actuator_id in self.actuators:
            logger.warning(f"Actuator {actuator_id} already exists")
            return False
                
        try:
            # Setup network first if needed
            if self.network is None:
                if not self.setup_network():
                    logger.error("Network setup failed")
                    return False
            
            # Create operation lock for this actuator
            self.operation_locks[actuator_id] = threading.Lock()
            
            # Create actuator instance
            logger.info(f"Creating actuator instance {actuator_id}")
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
            
            logger.info(f"Successfully added actuator {actuator_id}")
            return True
                
        except Exception as e:
            logger.error(f"Failed to add actuator {actuator_id}: {e}")
            print(traceback.format_exc())
            # Cleanup if failure
            if actuator_id in self.operation_locks:
                del self.operation_locks[actuator_id]
            return False
                
    def get_actuator(self, actuator_id: int) -> Optional[ElectrakMD]:
        """Get actuator instance by ID"""
        return self.actuators.get(actuator_id)

        
    async def move_multiple(self, target_position: float, target_speed: float):
        """Move multiple actuators simultaneously"""
        logger.info("Starting multiple actuator movement")
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
            logger.error(f"Multi-actuator movement error: {e}")
            return False
            
    def cleanup(self):
        """Cleanup all resources"""
        logger.info("Starting cleanup")
        try:
            # Stop all actuators
            for actuator in list(self.actuators.values()):
                try:
                    actuator.close()
                except Exception as e:
                    logger.error(f"Error cleaning up actuator: {e}")
            
            # Disconnect network
            if self.network:
                try:
                    self.network.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting network: {e}")
            
            # Shutdown thread pool
            try:
                self.executor.shutdown(wait=False)
            except Exception as e:
                logger.error(f"Error shutting down executor: {e}")
            
        finally:
            self.network = None
            self.actuators.clear()
            self.operation_locks.clear()
            logger.info("Cleanup complete")


    @classmethod
    def from_dict(cls, actuator_map: dict) -> 'ActuatorManager':
        try:
            hardware = actuator_map['hardware']
            parameters = hardware['parameters']
            devices = actuator_map['devices']
        except KeyError as e:
            logger.error(f"Missing required configuration field: {e}")
            raise
        try:
            manager = cls(**parameters)
            for device in devices:
                manager.add_actuator(device['mac'], device['node_id'])
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid battery configuration: {e}")
            raise ValueError(f"Failed to create battery definition: {e}")
        return manager


    @classmethod
    def from_json(cls, json_file: Union[Path, str]) -> "ActuatorManager":
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
        return cls.from_dict(data)
