from pathlib import Path
from typing import Dict, Optional
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
import canopen
from .electrak import ElectrakMD


class ActuatorManager:
    """Singleton manager for handling multiple actuators"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # Double-check pattern
                    cls._instance = super(ActuatorManager, cls).__new__(cls)
                    cls._instance.initialize()
        return cls._instance
            
    def initialize(self):
        """Initialize the manager's resources"""
        print("Initializing ActuatorManager")
        self.actuators: Dict[int, ElectrakMD] = {}
        self.network = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.connection_lock = threading.RLock()  # Using RLock instead of Lock
        self.operation_locks: Dict[int, threading.Lock] = {}
        
    def setup_network(self, channel: str = 'can0'):
        """Initialize CAN network connection"""
        print('Setting up network...')
        try:
            if self.network is None:
                print('Creating CAN network...')
                self.network = canopen.Network()
                print('Connecting to CAN bus...')
                self.network.connect(channel=channel, bustype='socketcan')
                print('CAN network setup complete')
            return True
        except Exception as e:
            print(f'Network setup failed: {e}')
            self.network = None
            return False
                
    def add_actuator(self, actuator_id: int, node_id: int):
        """Add a new actuator to the management system"""
        print(f"Adding actuator {actuator_id}")

        
        # Check if actuator already exists without lock
        if actuator_id in self.actuators:
            print(f"Actuator {actuator_id} already exists")
            return False
                
        try:
            # Setup network first if needed
            if self.network is None:
                if not self.setup_network():
                    print("Network setup failed")
                    return False
            
            # Create operation lock for this actuator
            self.operation_locks[actuator_id] = threading.Lock()
            
            # Create actuator instance
            print(f"Creating actuator instance {actuator_id}")
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            eds_file = str(base_dir / 'data' / 'canbus' / 'Electrak_MD.eds')

            actuator = ElectrakMD(
                network=self.network,
                node_id=node_id,
                eds_file=eds_file,
                operation_lock=self.operation_locks[actuator_id],
                executor=self.executor
            )
            
            # Add to actuators dict with lock
            with self.connection_lock:
                self.actuators[actuator_id] = actuator
            
            print(f"Successfully added actuator {actuator_id}")
            return True
                
        except Exception as e:
            print(f"Failed to add actuator {actuator_id}: {e}")
            # Cleanup if failure
            if actuator_id in self.operation_locks:
                del self.operation_locks[actuator_id]
            return False
                
    def get_actuator(self, actuator_id: int) -> Optional[ElectrakMD]:
        """Get actuator instance by ID"""
        return self.actuators.get(actuator_id)

        
    async def move_multiple(self, target_position: float, target_speed: float):
        """Move multiple actuators simultaneously"""
        print("Starting multiple actuator movement")
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
            print(f"Multi-actuator movement error: {e}")
            return False
            
    def cleanup(self):
        """Cleanup all resources"""
        print("Starting cleanup")
        try:
            # Stop all actuators
            for actuator in list(self.actuators.values()):
                try:
                    actuator.close()
                except Exception as e:
                    print(f"Error cleaning up actuator: {e}")
            
            # Disconnect network
            if self.network:
                try:
                    self.network.disconnect()
                except Exception as e:
                    print(f"Error disconnecting network: {e}")
            
            # Shutdown thread pool
            try:
                self.executor.shutdown(wait=False)
            except Exception as e:
                print(f"Error shutting down executor: {e}")
            
        finally:
            self.network = None
            self.actuators.clear()
            self.operation_locks.clear()
            print("Cleanup complete")
