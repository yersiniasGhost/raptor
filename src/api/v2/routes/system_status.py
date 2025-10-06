import csv
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from . import templates, get_auth_context
from utils.system_status import collect_system_stats
from hardware.power_5v.power_5v import Power5V
from database.database_manager import DatabaseManager

from utils import LogManager
logger = LogManager().get_logger(__name__)

router = APIRouter(prefix="/system-status", tags=["system-status"])
RAPTOR_SYSTEM = "RAPTOR"


@router.get("/")
async def system_status(request: Request):
    # Read the last N minutes of data
    timestamps, cpu_history, memory_history, disk_history = [], [], [], []
    try:
        with open(f'{RAPTOR_SYSTEM}_0.csv', 'r') as f:
            reader = csv.DictReader(f)
            data = list(reader)[-1500:]  # Last N entries
            timestamps = [row['Timestamp'] for row in data]
            cpu_history = [float(row['cpu_percent']) for row in data]
            memory_history = [float(row['memory_percent']) for row in data]
            disk_history = [float(row['disk_percent']) for row in data]
    except Exception as e:
        logger.error(f"Error collecting historical system status: {e}")

    active_pids, dead_pids = Power5V().get_process_states()
    power_state = Power5V().check_state()

    # Get queued IoT messages count
    queued_messages = 0
    try:
        db = DatabaseManager()
        queued_messages = db.count_stored_telemetry_data()
    except Exception as e:
        logger.error(f"Error getting queued message count: {e}")

    try:
        current_stats = collect_system_stats()

        return templates.TemplateResponse("system_status.html", {
            "request": request,
            "power5v_state": power_state,
            "dead_requests": len(dead_pids),
            "on_requests": len(active_pids),
            "queued_messages": queued_messages,
            "current_stats": current_stats,
            "timestamps": timestamps,
            "cpu_history": cpu_history,
            "memory_history": memory_history,
            "disk_history": disk_history,
            **get_auth_context(request)
        })
    except Exception as e:
        logger.error(f"Error collecting system status: {e}")
        return templates.TemplateResponse("system_status.html", {
            "request": request,
            "error": str(e),
            "queued_messages": 0,
            "current_stats": [],
            "timestamps": [],
            "cpu_history": [],
            "memory_history": [],
            "disk_history": [],
            **get_auth_context(request)
        })


@router.post("/clear-requests")
async def clear_requests():
    """Clear dead power requests and log current power state"""
    try:
        power5v = Power5V()
        dead_pids = power5v.cleanup_dead_processes()
        power5v.log_current_power_state()
        
        logger.info(f"Cleared {len(dead_pids)} dead power requests: {dead_pids}")
        
        return JSONResponse(content={
            "success": True,
            "message": f"Successfully cleared {len(dead_pids)} dead power requests",
            "cleared_pids": dead_pids
        })
    except Exception as e:
        logger.error(f"Error clearing requests: {e}")
        return JSONResponse(content={
            "success": False,
            "message": f"Error clearing requests: {str(e)}"
        }, status_code=500)
