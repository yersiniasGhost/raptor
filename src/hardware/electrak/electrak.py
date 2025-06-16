from typing import Optional, List, Dict, Any
import canopen
import time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import asyncio
import threading
from hardware.hardware_base import HardwareBase
from utils import LogManager


class ElectrakMD(HardwareBase):
    @dataclass
    class MotionFlags:
        """Motion status flags from object 0x2203"""
        IN_MOTION: bool = False
        MANUAL_MODE: bool = False
        OVERRIDE_MODE: bool = False
        AT_ZERO: bool = False
        AT_MAXIMUM: bool = False
        BEYOND_LIMIT: bool = False
        MOVING_POSITIVE: bool = False
        MOVING_NEGATIVE: bool = False

    @dataclass
    class ErrorFlags:
        """Error flags from object 0x2204"""
        OVERCURRENT: bool = False
        THERMAL_SWITCH: bool = False
        OVERVOLTAGE: bool = False
        UNDERVOLTAGE: bool = False
        MEMORY_ERROR: bool = False
        FEEDBACK_ERROR: bool = False
        WATCHDOG: bool = False
        STROKE_AREA: bool = False

    """Enhanced actuator class for multi-actuator system"""
    def __init__(self, network: canopen.Network, node_id: int, 
                 eds_file: str, operation_lock: threading.Lock,
                 executor: ThreadPoolExecutor):
        self.logger = LogManager().get_logger("Electrak")
        self.network = network
        self.node_id = node_id
        self.operation_lock = operation_lock
        self._executor = executor
        self.is_moving = False
        
        # Add node to existing network
        self.node = self.network.add_node(node_id, eds_file)
        
        # Object dictionary entries
        self.OD = {
            'TARGET_POSITION': 0x2100,
            'CURRENT_LIMIT': 0x2101,
            'TARGET_SPEED': 0x2102,
            'MOVEMENT_PROFILE': 0x2103,
            'CONTROL_BITS': 0x2104,
            'MEASURED_POSITION': 0x2200,
            'MEASURED_CURRENT': 0x2201,
            'MEASURED_SPEED': 0x2202,
            'MOTION_FLAGS': 0x2203,
            'ERROR_FLAGS': 0x2204,
            'STROKE': 0x2007,
            'MAX_CURRENT': 0x2008,
            'TEMPERATURE': 0x200F,
            'VOLTAGE': 0x2010
        }
        self.is_setup: bool = False


    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        return {d['mac']: "Get_Identifier_NA" for d in devices}


    def setup(self):
        if not self.is_setup:
            self.logger.info("Electrak Setup")
            """Initialize the actuator with error handling"""
            with self.operation_lock:
                try:
                    self.node.nmt.state = 'PRE-OPERATIONAL'
                    time.sleep(0.25)

                    self.node.nmt.state = 'OPERATIONAL'
                    time.sleep(0.25)

                    # Configure PDO timing
                    self.node.sdo[0x2006].raw = 100

                    if self.node.nmt.state != 'OPERATIONAL':
                        raise RuntimeError("Failed to enter operational state")
                except Exception as e:
                    self.logger.error(f"Actuator setup error: {e}", exc_info=True)
                    raise
        self.is_setup = True

    def current_state(self) -> dict:
        self.setup()
        """Get current state with improved SDO handling and retries"""
        max_retries = 1
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                position = self.get_position()
                with self.operation_lock:  # Ensure exclusive SDO access
                    output = {
                        "position": position,
                        "current": self.node.sdo[self.OD['MEASURED_CURRENT']].raw/10,
                        "speed": self.node.sdo[self.OD['MEASURED_SPEED']].raw/10,
                        "voltage": self.node.sdo[self.OD['VOLTAGE']].raw/10
                    }
                    return output
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                # On final attempt, return safe values
                return {
                    "position": self.get_position() or -90.0,
                    "current": -90.0,
                    "speed": -90.0,
                    "voltage": -90.0
                }


    def set_pdo_timeout(self, timeout_ms: int = 5000):
        self.setup()
        """Set the PDO timeout value"""
        try:
            self.node.sdo[0x2005].raw = timeout_ms
            print(f"PDO timeout set to {timeout_ms}ms")
            return True
        except Exception as e:
            print(f"Failed to set PDO timeout: {e}")
            return False



    async def move_to(self, target_position: float, target_speed: float) -> bool:
        """
        Non-blocking movement command with proper complete handling and thread safety
        """
        self.setup()
        if self.is_moving:
            print("Movement already in progress")
            return False

        try:
            with self.operation_lock:
                error_status = self.get_error_status()
                if error_status and any(vars(error_status).values()):
                    print("Clearing existing errors before movement...")
                    if not self.clear_errors():
                        raise RuntimeError("Failed to clear existing errors")
                    time.sleep(1.0)  # Wait for system to stabilize

            self.is_moving = True
            # Start movement command in a separate thread
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, self.move_pdo, target_position, target_speed, 3.5)
            print("Movement completed with result: ", result)
            return result

        except Exception as e:
            self.is_moving = False
            print(f"Movement error: {e}")
            return False
        finally:
            self.is_moving = False


    def move_pdo(self, position_mm: int, speed_percent: int = 80, current_limit: float = 3.5):
        """
        Move actuator using PDO messaging with continuous updates
        """
        self.setup()
        movement_successful = False
        cob_id = 0x200 + self.node_id
        pdo_data = bytearray(8)

        try:
            print("\nStarting move sequence...")
            # with self.operation_lock:
            current_pos = self.get_position()
            if current_pos is None:
                print("Failed to read initial position.")
                return False

            print(f"Current position: {current_pos:.1f}mm")
            print(f"Target position: {position_mm}mm")
            print(f"Distance to move: {abs(position_mm - current_pos):.1f}mm")
            
            # Clear any existing errors
            error_status = self.get_error_status()
            if error_status and any(vars(error_status).values()):
                print("\nClearing errors before motion...")
                if not self.clear_errors():
                    raise RuntimeError("Failed to clear errors")
                time.sleep(0.5)
            
            # Set longer PDO timeout
            with self.operation_lock:
                self.set_pdo_timeout(65535)  # 100 seconds
            
            # Convert values to actuator units
            position = int(position_mm * 10)
            speed = int(speed_percent * 10)
            current = int(current_limit * 10)

            # Create PDO message
            pdo_data[0:2] = position.to_bytes(2, byteorder='little', signed=True)
            pdo_data[2:4] = current.to_bytes(2, byteorder='little', signed=True)
            pdo_data[4:6] = speed.to_bytes(2, byteorder='little', signed=True)
            pdo_data[6] = 0  # Normal operation mode
            pdo_data[7] = 1  # Enable the bit ON

            # Send initial command
            print("\nSending motion command")
            self.network.send_message(cob_id, pdo_data)

            # Monitor motion with continuous PDO updates
            start_time = time.time()
            last_pos = current_pos
            stable_position_count = 0
            position_tolerance = 1.0  # mm
            stable_count_required = 3  # Number of stable readings required
            update_interval = 2.0
            error_recovery_attempts = 0
            max_error_recovery_attempts = 3

            while True:
                time.sleep(update_interval)  # Small delay between checks

                current_time = time.time()
                current_pos = self.get_position()
                # current_pos = None
                # with self.operation_lock:
                #     current_pos = self.get_position()
                
                if current_pos is None:
                    continue
                # consider LOG:
                # print(f"Position: {current_pos:.1f}mm, "
                #       f"Current: {self.node.sdo[self.OD['MEASURED_CURRENT']].raw/10:.1f}A")
                
                # Check for errors
                with self.operation_lock:
                    error_status = self.get_error_status()
                    if error_status and any(vars(error_status).values()):
                        error_flags = [k for k, v in vars(error_status).items() if v]
                        print(f"Error detected: {error_flags}")
                        if 'FEEDBACK_ERROR' in error_flags:
                            error_recovery_attempts += 1
                            if error_recovery_attempts > max_error_recovery_attempts:
                                print("Max error recovery attempts reached")
                                break
                                
                            print(f"Attempting error recovery ({error_recovery_attempts}/{max_error_recovery_attempts})")
                            if not self.clear_errors():
                                print("Error recovery failed")
                                break
                                
                            # Resend movement command after error recovery
                            time.sleep(1.0)
                            self.set_pdo_timeout(65535)
                            self.network.send_message(cob_id, pdo_data)
                            continue

                # Check if we've reached target
                if abs(current_pos - position_mm) < position_tolerance:
                    stable_position_count += 1
                    print(f"At target position: {current_pos:.1f}mm (stability count: {stable_position_count})")
                    if stable_position_count >= stable_count_required:
                        print(f"Movement completed successfully at position: {current_pos:.1f}mm")
                        movement_successful = True
                        return True
                else:
                    stable_position_count = 0
                
                # Check for motion stall
                if abs(current_pos - last_pos) < 0.1:
                    if current_time - start_time > 30.0:  # Overall timeout
                        print("Motion timed out - no position change")
                        return False
                else:
                    start_time = current_time  # Reset timeout if moving
                    
                last_pos = current_pos

        except Exception as e:
            print(f"Motion control error: {e}")

        finally:
            print("Starting cleanup sequence...")
            cleanup_successful = False
            cleanup_attempts = 0
            max_cleanup_attempts = 3
            while not cleanup_successful and cleanup_attempts < max_cleanup_attempts:
                try:
                    cleanup_attempts += 1
                    print(f"Cleanup attempt {cleanup_attempts}")
                    
                    # 1. Clear enable the bit with timeout
                    if pdo_data:
                        pdo_data[7] = 0
                        self.network.send_message(cob_id, pdo_data)
                    
                    # 2. Quick state transition to stop movement
                    self._safe_state_transition('PRE-OPERATIONAL', timeout=0.5)
                    self._safe_state_transition('OPERATIONAL', timeout=0.5)
                    
                    cleanup_successful = True
                    print("Cleanup completed successfully")
                    return movement_successful

                except Exception as e:
                    print(f"Cleanup attempt {cleanup_attempts} failed: {e}")
                    if cleanup_attempts >= max_cleanup_attempts:
                        print("Max cleanup attempts reached")
            
            return False  # Return False on error cases



    def get_position(self) -> Optional[float]:
        """Get measured position with retries"""
        self.setup()
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with self.operation_lock:  # Ensure exclusive SDO access
                    position_raw = self.node.sdo[self.OD['MEASURED_POSITION']].raw
                    return position_raw / 10.0
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
        return None



    def get_position_no_lock(self) -> Optional[float]:
        """
        Get measured position

        Returns:
            float: Position in mm, or None if error
        """
        self.setup()
        try:
            position_raw = self.node.sdo[self.OD['MEASURED_POSITION']].raw
            return position_raw / 10.0  # Convert from 0.1mm to mm
        except Exception as e:
            print(f"Position read error: {e}")
            return None

    def get_motion_status(self) -> Optional[MotionFlags]:
        """Get motion status flags"""
        try:
            status = self.node.sdo[self.OD['MOTION_FLAGS']].raw
            return self.MotionFlags(
                IN_MOTION=bool(status & 0x01),
                MANUAL_MODE=bool(status & 0x02),
                OVERRIDE_MODE=bool(status & 0x04),
                AT_ZERO=bool(status & 0x08),
                AT_MAXIMUM=bool(status & 0x10),
                BEYOND_LIMIT=bool(status & 0x20),
                MOVING_POSITIVE=bool(status & 0x40),
                MOVING_NEGATIVE=bool(status & 0x80)
            )
        except Exception as e:
            print(f"Motion status read error: {e}")
            return None


    def get_error_status(self) -> Optional[ErrorFlags]:
        self.setup()
        """Get error status flags"""
        try:
            flags = self.node.sdo[self.OD['ERROR_FLAGS']].raw
            return self.ErrorFlags(
                OVERCURRENT=bool(flags & 0x01),
                THERMAL_SWITCH=bool(flags & 0x02),
                OVERVOLTAGE=bool(flags & 0x04),
                UNDERVOLTAGE=bool(flags & 0x08),
                MEMORY_ERROR=bool(flags & 0x10),
                FEEDBACK_ERROR=bool(flags & 0x20),
                WATCHDOG=bool(flags & 0x40),
                STROKE_AREA=bool(flags & 0x80)
            )
        except Exception as e:
            print(f"Error status read error: {e}")
            return None


    def check_current_state(self):
        self.setup()
        """Check all relevant parameters for current status"""
        try:
            print("\nCurrent State Check:")
            # Check max allowed current
            max_current = self.node.sdo[self.OD['MAX_CURRENT']].raw
            print(f"Max allowed current: {max_current/10:.1f}A")
            
            # Check current limit setting
            current_limit = self.node.sdo[self.OD['CURRENT_LIMIT']].raw
            print(f"Current limit setting: {current_limit/10:.1f}A")
            
            # Check measured current
            measured_current = self.node.sdo[self.OD['MEASURED_CURRENT']].raw
            print(f"Measured current: {measured_current/10:.1f}A")
            
            # Get error status
            error_status = self.get_error_status()
            if error_status:
                print("Error flags:", [k for k, v in vars(error_status).items() if v])
                
            return True
        except Exception as e:
            print(f"State check error: {e}")
            return False


    def get_diagnostics(self) -> Optional[dict]:
        self.setup()
        """
        Get comprehensive diagnostic information
        
        Returns:
            dict: Dictionary containing all diagnostic values, or None if error
        """
        try:
            return {
                'position_mm': self.get_position(),
                'current_A': self.node.sdo[self.OD['MEASURED_CURRENT']].raw / 10.0,
                'speed_percent': self.node.sdo[self.OD['MEASURED_SPEED']].raw / 10.0,
                'temperature_C': self.node.sdo[self.OD['TEMPERATURE']].raw,
                'voltage_V': self.node.sdo[self.OD['VOLTAGE']].raw / 10.0,
                'stroke_mm': self.node.sdo[self.OD['STROKE']].raw / 10.0,
                'motion_status': self.get_motion_status(),
                'error_status': self.get_error_status()
            }
        except Exception as e:
            print(f"Diagnostics read error: {e}")
            return None


    def _safe_state_transition(self, target_state: str, timeout: float = 0.5):
        """
        Perform NMT state transition with timeout
        """
        try:
            self.node.nmt.state = target_state
            time.sleep(min(timeout, 0.5))  # Cap timeout at 0.5 seconds
        except Exception as e:
            print(f"State transition to {target_state} failed: {e}")


    def clear_errors(self):
        """Enhanced error clearing with verification"""
        self.setup()
        try:
            print("Attempting to clear errors...")
            # Send NMT reset
            self.node.nmt.state = 'RESET'
            time.sleep(0.5)

            # Return to operational
            self.node.nmt.state = 'PRE-OPERATIONAL'
            time.sleep(0.5)
            self.node.nmt.state = 'OPERATIONAL'
            time.sleep(0.5)

            # Verify errors are cleared
            error_status = self.get_error_status()
            if error_status and any(vars(error_status).values()):
                print("Failed to clear errors")
                return False

            print("Errors cleared successfully")
            return True
        except Exception as e:
            print(f"Error clearing failed: {e}")
            return False


    def close(self):
        """Clean up and close connection"""
        try:
            self._safe_state_transition('PRE-OPERATIONAL', timeout=0.2)
        except Exception as e:
            print(f"Cleanup error: {e}")

    def data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str]):
        pass

    def get_points(self, names: List[str]) -> List:
        pass
