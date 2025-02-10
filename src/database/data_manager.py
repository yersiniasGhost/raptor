import sqlite3
import time


class DataManager:

    def __init__(self, db_path: str, batch_size: int = 1000):
        self.db_path = db_path
        self.batch_size = batch_size



    async def store_data(self, point_id: int, value: float):
        """Store single data point"""
        timestamp = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO data_points VALUES (?, ?, ?)",
                (timestamp, point_id, value)
            )



    async def batch_store_data(self, data_points: list):
        """Store multiple data points efficiently"""
        timestamp = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT INTO data_points VALUES (?, ?, ?)",
                [(timestamp, p_id, value) for p_id, value in data_points]
            )



    async def upload_and_clear(self):
        """Upload data to cloud and clear if successful"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get data in batches
                cursor = conn.execute(
                    "SELECT * FROM data_points ORDER BY timestamp LIMIT ?",
                    (self.batch_size,)
                )
                batch = cursor.fetchall()

                while batch:
                    # Upload batch to cloud
                    success = await self._upload_to_cloud(batch)

                    if success:
                        # Delete uploaded data
                        oldest_timestamp = batch[-1][0]
                        conn.execute(
                            "DELETE FROM data_points WHERE timestamp <= ?",
                            (oldest_timestamp,)
                        )
                        conn.commit()

                        # Get next batch
                        batch = cursor.fetchall()
                    else:
                        break  # Stop if upload fails

                # Optionally vacuum database to reclaim space
                conn.execute("VACUUM")

        except Exception as e:
            logging.error(f"Error in upload_and_clear: {e}")
            raise



    async def cleanup_old_data(self, hours: int = 24):
        """Remove data older than specified hours"""
        cutoff = int(time.time()) - (hours * 3600)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM data_points WHERE timestamp < ?",
                (cutoff,)
            )