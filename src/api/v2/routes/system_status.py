import csv
from fastapi import APIRouter, Request
from . import templates
from utils.system_status import collect_system_stats

from utils import LogManager
logger = LogManager().get_logger(__name__)

router = APIRouter(prefix="/system-status", tags=["system-status"])


@router.get("/")
async def system_status(request: Request):
    # Read the last 60 minutes of data
    data = []
    with open('system_0.csv', 'r') as f:
        reader = csv.DictReader(f)
        data = list(reader)[-1500:]  # Last 60 entries

    current_stats = data[-1] if data else collect_system_stats()

    timestamps = [row['Timestamp'] for row in data]
    cpu_history = [float(row['cpu_percent']) for row in data]
    memory_history = [float(row['memory_percent']) for row in data]

    return templates.TemplateResponse("system_status.html", {
        "request": request,
        "current_stats": current_stats,
        "timestamps": timestamps,
        "cpu_history": cpu_history,
        "memory_history": memory_history
    })

