from typing import Optional, List, Dict, Any, Tuple
import psutil
import time
import os
from datetime import datetime, timedelta
from database.database_manager import DatabaseManager
from utils import LogManager, Singleton
import sqlite3


class HardwareResourceLockManager(metaclass=Singleton):
    """
    Exclusive hardware resource lock manager for coordinating access across processes.

    Unlike Power5V which uses reference counting for shared resources, this provides
    exclusive access control where only one process can hold a resource lock at a time.
    Other processes queue up and wait their turn.
    """

    DEFAULT_TIMEOUT = 30.0  # Default timeout in seconds
    CLEANUP_INTERVAL = 60   # Cleanup dead processes every 60 seconds

    def __init__(self):
        self.logger = LogManager().get_logger("HardwareResourceLockManager")
        self.last_cleanup = time.time()

    def acquire_lock(self, resource_key: str, timeout: float = None,
                    process_id: int = None, lock_info: str = None) -> bool:
        """
        Acquire exclusive lock on a hardware resource.

        Args:
            resource_key: Unique identifier for resource (e.g., "modbus_rtu:/dev/ttyUSB0")
            timeout: Maximum time to wait for lock (default: DEFAULT_TIMEOUT)
            process_id: Process ID requesting lock (default: current PID)
            lock_info: Optional description of lock purpose

        Returns:
            bool: True if lock acquired successfully, False if timeout
        """
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT

        if process_id is None:
            process_id = os.getpid()

        self.logger.info(f"PID {process_id} requesting lock on '{resource_key}' (timeout: {timeout}s)")

        # Cleanup dead processes periodically
        self._cleanup_if_needed()

        start_time = time.time()
        timeout_at = datetime.now() + timedelta(seconds=timeout)

        db = DatabaseManager()

        try:
            # First, try to acquire lock immediately
            if self._try_acquire_immediate(db, resource_key, process_id, timeout, lock_info):
                self.logger.info(f"PID {process_id} acquired lock on '{resource_key}' immediately")
                return True

            # If immediate acquisition failed, join the queue
            queue_id = self._join_queue(db, resource_key, process_id, timeout_at)
            if not queue_id:
                self.logger.warning(f"PID {process_id} failed to join queue for '{resource_key}'")
                return False

            self.logger.info(f"PID {process_id} joined queue for '{resource_key}' (position will be calculated)")

            # Wait in queue with periodic checks
            while time.time() - start_time < timeout:
                # Check if it's our turn
                if self._try_acquire_from_queue(db, resource_key, process_id, timeout, lock_info):
                    # Remove from queue since we got the lock
                    self._remove_from_queue(db, queue_id)
                    self.logger.info(f"PID {process_id} acquired lock on '{resource_key}' from queue")
                    return True

                # Log queue position periodically
                position = self._get_queue_position(db, resource_key, process_id)
                if position > 0:
                    self.logger.debug(f"PID {process_id} waiting for '{resource_key}', position {position} in queue")

                # Short sleep before trying again
                time.sleep(0.5)

            # Timeout reached, remove from queue
            self._remove_from_queue(db, queue_id)
            self.logger.warning(f"PID {process_id} timeout waiting for lock on '{resource_key}'")
            return False

        except Exception as e:
            self.logger.error(f"Error acquiring lock on '{resource_key}': {e}")
            return False

    def release_lock(self, resource_key: str, process_id: int = None) -> bool:
        """
        Release exclusive lock on a hardware resource.

        Args:
            resource_key: Resource identifier to release
            process_id: Process ID releasing lock (default: current PID)

        Returns:
            bool: True if lock released successfully
        """
        if process_id is None:
            process_id = os.getpid()

        self.logger.info(f"PID {process_id} releasing lock on '{resource_key}'")

        db = DatabaseManager()

        try:
            cursor = db.connection.cursor()

            # Remove the lock - only if we own it
            cursor.execute("""
                DELETE FROM hardware_resource_locks
                WHERE resource_key = ? AND owner_pid = ?
            """, (resource_key, process_id))

            rows_affected = cursor.rowcount
            db.connection.commit()

            if rows_affected > 0:
                self.logger.info(f"PID {process_id} successfully released lock on '{resource_key}'")
                return True
            else:
                self.logger.warning(f"PID {process_id} tried to release lock on '{resource_key}' but didn't own it")
                return False

        except sqlite3.Error as e:
            db.connection.rollback()
            self.logger.error(f"Database error releasing lock on '{resource_key}': {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error releasing lock on '{resource_key}': {e}")
            return False

    def is_locked(self, resource_key: str) -> bool:
        """
        Check if a resource is currently locked.

        Args:
            resource_key: Resource identifier to check

        Returns:
            bool: True if resource is locked
        """
        db = DatabaseManager()

        try:
            cursor = db.connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM hardware_resource_locks
                WHERE resource_key = ? AND expires_at > CURRENT_TIMESTAMP
            """, (resource_key,))

            count = cursor.fetchone()[0]
            return count > 0

        except Exception as e:
            self.logger.error(f"Error checking lock status for '{resource_key}': {e}")
            return False

    def get_lock_owner(self, resource_key: str) -> Optional[int]:
        """
        Get the PID of the process that owns the lock on a resource.

        Args:
            resource_key: Resource identifier to check

        Returns:
            Optional[int]: PID of lock owner, or None if not locked
        """
        db = DatabaseManager()

        try:
            cursor = db.connection.cursor()
            cursor.execute("""
                SELECT owner_pid FROM hardware_resource_locks
                WHERE resource_key = ? AND expires_at > CURRENT_TIMESTAMP
            """, (resource_key,))

            result = cursor.fetchone()
            return result[0] if result else None

        except Exception as e:
            self.logger.error(f"Error getting lock owner for '{resource_key}': {e}")
            return None

    def get_queue_status(self, resource_key: str) -> List[Dict[str, Any]]:
        """
        Get the current queue status for a resource.

        Args:
            resource_key: Resource identifier to check

        Returns:
            List[Dict]: List of queued processes with their info
        """
        db = DatabaseManager()

        try:
            cursor = db.connection.cursor()
            cursor.execute("""
                SELECT waiting_pid, queued_at, timeout_at, priority
                FROM hardware_lock_queue
                WHERE resource_key = ? AND timeout_at > CURRENT_TIMESTAMP
                ORDER BY priority DESC, queued_at ASC
            """, (resource_key,))

            results = cursor.fetchall()
            queue_status = []

            for i, row in enumerate(results):
                queue_status.append({
                    'position': i + 1,
                    'pid': row[0],
                    'queued_at': row[1],
                    'timeout_at': row[2],
                    'priority': row[3]
                })

            return queue_status

        except Exception as e:
            self.logger.error(f"Error getting queue status for '{resource_key}': {e}")
            return []

    def force_release_lock(self, resource_key: str, admin_override: bool = False) -> bool:
        """
        Force release a lock (admin function for stuck locks).

        Args:
            resource_key: Resource identifier to force release
            admin_override: Must be True to confirm admin action

        Returns:
            bool: True if lock was force released
        """
        if not admin_override:
            self.logger.warning(f"Attempted force release without admin override for '{resource_key}'")
            return False

        self.logger.warning(f"ADMIN: Force releasing lock on '{resource_key}'")

        db = DatabaseManager()

        try:
            cursor = db.connection.cursor()

            # Get current lock owner for logging
            cursor.execute("""
                SELECT owner_pid FROM hardware_resource_locks
                WHERE resource_key = ?
            """, (resource_key,))

            result = cursor.fetchone()
            if result:
                old_owner = result[0]
                self.logger.warning(f"ADMIN: Forcibly releasing lock owned by PID {old_owner}")

            # Remove the lock
            cursor.execute("""
                DELETE FROM hardware_resource_locks
                WHERE resource_key = ?
            """, (resource_key,))

            rows_affected = cursor.rowcount
            db.connection.commit()

            if rows_affected > 0:
                self.logger.warning(f"ADMIN: Successfully force released lock on '{resource_key}'")
                return True
            else:
                self.logger.info(f"ADMIN: No lock found to release on '{resource_key}'")
                return False

        except Exception as e:
            self.logger.error(f"Error force releasing lock on '{resource_key}': {e}")
            return False

    def cleanup_dead_processes(self) -> int:
        """
        Clean up locks and queue entries for dead processes.

        Returns:
            int: Number of dead process entries cleaned up
        """
        self.logger.info("Starting cleanup of dead processes")

        db = DatabaseManager()
        cleanup_count = 0

        try:
            cursor = db.connection.cursor()

            # Get all PIDs from locks and queue
            cursor.execute("""
                SELECT DISTINCT owner_pid FROM hardware_resource_locks
                UNION
                SELECT DISTINCT waiting_pid FROM hardware_lock_queue
            """)

            all_pids = [row[0] for row in cursor.fetchall()]
            dead_pids = []

            # Check which PIDs are dead
            for pid in all_pids:
                try:
                    if not psutil.pid_exists(pid):
                        dead_pids.append(pid)
                    else:
                        # Double-check the process is actually running
                        process = psutil.Process(pid)
                        if process.status() == psutil.STATUS_ZOMBIE:
                            dead_pids.append(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    dead_pids.append(pid)

            # Clean up dead processes
            for pid in dead_pids:
                # Remove locks owned by dead process
                cursor.execute("""
                    DELETE FROM hardware_resource_locks
                    WHERE owner_pid = ?
                """, (pid,))
                lock_cleanup = cursor.rowcount

                # Remove queue entries for dead process
                cursor.execute("""
                    DELETE FROM hardware_lock_queue
                    WHERE waiting_pid = ?
                """, (pid,))
                queue_cleanup = cursor.rowcount

                if lock_cleanup > 0 or queue_cleanup > 0:
                    self.logger.info(f"Cleaned up dead PID {pid}: {lock_cleanup} locks, {queue_cleanup} queue entries")
                    cleanup_count += lock_cleanup + queue_cleanup

            # Also cleanup expired locks and queue entries
            cursor.execute("""
                DELETE FROM hardware_resource_locks
                WHERE expires_at <= CURRENT_TIMESTAMP
            """)
            expired_locks = cursor.rowcount

            cursor.execute("""
                DELETE FROM hardware_lock_queue
                WHERE timeout_at <= CURRENT_TIMESTAMP
            """)
            expired_queue = cursor.rowcount

            if expired_locks > 0 or expired_queue > 0:
                self.logger.info(f"Cleaned up expired entries: {expired_locks} locks, {expired_queue} queue entries")
                cleanup_count += expired_locks + expired_queue

            db.connection.commit()

            if cleanup_count > 0:
                self.logger.info(f"Cleanup completed: {cleanup_count} total entries removed")

            return cleanup_count

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            return 0

    def _cleanup_if_needed(self):
        """Perform cleanup if enough time has passed since last cleanup."""
        current_time = time.time()
        if current_time - self.last_cleanup > self.CLEANUP_INTERVAL:
            self.cleanup_dead_processes()
            self.last_cleanup = current_time

    def _try_acquire_immediate(self, db: DatabaseManager, resource_key: str,
                              process_id: int, timeout: float, lock_info: str = None) -> bool:
        """Try to acquire lock immediately without queuing."""
        try:
            cursor = db.connection.cursor()
            expires_at = datetime.now() + timedelta(seconds=timeout)

            cursor.execute("""
                INSERT INTO hardware_resource_locks
                (resource_key, owner_pid, expires_at, lock_info)
                VALUES (?, ?, ?, ?)
            """, (resource_key, process_id, expires_at, lock_info))

            db.connection.commit()
            return True

        except sqlite3.IntegrityError:
            # Resource already locked
            db.connection.rollback()
            return False
        except Exception as e:
            db.connection.rollback()
            self.logger.error(f"Error in immediate acquire: {e}")
            return False

    def _join_queue(self, db: DatabaseManager, resource_key: str,
                   process_id: int, timeout_at: datetime) -> Optional[int]:
        """Join the queue for a locked resource."""
        try:
            cursor = db.connection.cursor()

            cursor.execute("""
                INSERT INTO hardware_lock_queue
                (resource_key, waiting_pid, timeout_at)
                VALUES (?, ?, ?)
            """, (resource_key, process_id, timeout_at))

            queue_id = cursor.lastrowid
            db.connection.commit()
            return queue_id

        except Exception as e:
            db.connection.rollback()
            self.logger.error(f"Error joining queue: {e}")
            return None

    def _try_acquire_from_queue(self, db: DatabaseManager, resource_key: str,
                               process_id: int, timeout: float, lock_info: str = None) -> bool:
        """Try to acquire lock if we're first in queue and resource is free."""
        try:
            cursor = db.connection.cursor()

            # Check if we're first in queue
            cursor.execute("""
                SELECT waiting_pid FROM hardware_lock_queue
                WHERE resource_key = ? AND timeout_at > CURRENT_TIMESTAMP
                ORDER BY priority DESC, queued_at ASC
                LIMIT 1
            """, (resource_key,))

            result = cursor.fetchone()
            if not result or result[0] != process_id:
                return False  # Not our turn yet

            # Try to acquire the lock
            return self._try_acquire_immediate(db, resource_key, process_id, timeout, lock_info)

        except Exception as e:
            self.logger.error(f"Error trying acquire from queue: {e}")
            return False

    def _remove_from_queue(self, db: DatabaseManager, queue_id: int):
        """Remove entry from queue."""
        try:
            cursor = db.connection.cursor()
            cursor.execute("""
                DELETE FROM hardware_lock_queue WHERE id = ?
            """, (queue_id,))
            db.connection.commit()
        except Exception as e:
            self.logger.error(f"Error removing from queue: {e}")

    def _get_queue_position(self, db: DatabaseManager, resource_key: str, process_id: int) -> int:
        """Get position in queue (1-based, 0 if not in queue)."""
        try:
            cursor = db.connection.cursor()
            cursor.execute("""
                SELECT ROW_NUMBER() OVER (ORDER BY priority DESC, queued_at ASC) as position,
                       waiting_pid
                FROM hardware_lock_queue
                WHERE resource_key = ? AND timeout_at > CURRENT_TIMESTAMP
            """, (resource_key,))

            for position, pid in cursor.fetchall():
                if pid == process_id:
                    return position

            return 0  # Not in queue

        except Exception as e:
            self.logger.error(f"Error getting queue position: {e}")
            return 0