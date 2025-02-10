from apscheduler.schedulers.background import BackgroundScheduler
import time
import logging

# Configure logging
logging.basicConfig(filename='/var/log/data_acquisition.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def acquire_and_upload():
    logging.info("Acquiring data and uploading...")
    # Your data acquisition logic here
    try:
        # Simulated data collection and upload
        logging.info("Data collected successfully")
    except Exception as e:
        logging.error(f"Error during data acquisition: {e}")


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(acquire_and_upload, 'interval', minutes=5)
    scheduler.start()

    logging.info("Data acquisition service started.")

    try:
        while True:
            time.sleep(1)  # Keep the script running
    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutting down scheduler.")
        scheduler.shutdown()
