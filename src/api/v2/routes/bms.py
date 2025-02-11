# routes/bms.py
import subprocess
from datetime import datetime
from typing import Tuple, Optional, List, Dict
from typing import Annotated
from collections import deque
import json
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from . import templates
import logging
from communications.modbus.modbus import modbus_data_acquisition, ModbusMap
from bms_store import BMSDataStore
from .hardware_deployment import HardwareDeployment, get_hardware
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bms", tags=["bms"])

bms_store = BMSDataStore()

BASE_DIR = Path(__file__).resolve().parent


def parse_timestamp(timestamp_str: str) -> datetime:
    """Convert timestamp string to datetime object."""
    return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')


def linear_regression(x: List[float], y: List[float]) -> float:
    """
    Calculate linear regression slope using least squares method.
    Returns the slope (rate of change).
    """
    n = len(x)
    if n < 2:
        return 0.0
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
    print(denominator, "d")
    if abs(denominator) < 1e-10:
        return 0.0
    return numerator / denominator


def calculate_soc_trend(trend_data: List[Dict]) -> float:
    """
    Calculate the trend in SOC/Capacity data using linear regression.
    Returns the slope in capacity units per hour.
    """
    timestamps = [data_dict["Timestamp"] for data_dict in trend_data]
    capacities = [float(data_dict["Capacity"]) for data_dict in trend_data]
    if len(timestamps) < 2:
        return 0.0

    # Convert timestamps to hours since start
    base_time = parse_timestamp(timestamps[0])
    hours_elapsed = [(parse_timestamp(t) - base_time).total_seconds() / 3600
                     for t in timestamps]

    # Calculate trend using linear regression
    return linear_regression(hours_elapsed, capacities)


def calculate_charge_projections(current_soc: float, trend_per_hour: float) -> Tuple[Optional[float], float, float]:
    """
    Calculate charging projections based on current SOC and trend.

    Returns:
    Tuple containing:
    - Time to 100% in hours, if trend is negative then time to 20%
    - SOC after 1 hour
    - SOC after 2 hours
    """

    if trend_per_hour < 0:
        soc_remaining = current_soc - 20.0
        hours_to_go = -soc_remaining / trend_per_hour
    elif trend_per_hour > 0:
        # Calculate time to reach 100%
        soc_remaining = 100.0 - current_soc
        hours_to_go = soc_remaining / trend_per_hour
    else:
        soc_remaining = -1
        hours_to_go = -1

    # Calculate future SOC values
    soc_1hr = min(100.0, current_soc + trend_per_hour)
    soc_2hr = min(100.0, current_soc + (2 * trend_per_hour))

    return hours_to_go, soc_1hr, soc_2hr


def format_time_to_full(hours: Optional[float]) -> str:
    total_minutes = int(hours * 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours == 0:
        return f"{minutes}min"
    return f"{hours}h {minutes}min"


def read_last_n_tail(filepath: str, n: int = 5) -> List[Dict]:
    """
    Read last n rows using system tail command.
    """
    try:
        with open(filepath, 'r') as f:
            header = f.readline().strip().split(',')

        # Use tail command
        result = subprocess.run(
            ['tail', f'-n{n}', filepath],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"tail command failed: {result.stderr}")

        lines = result.stdout.strip().splitlines()
        return [dict(zip(header, line.split(','))) for line in lines]

    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {filepath}")
    except Exception as e:
        raise Exception(f"Error reading file: {str(e)}")


def get_batteries(deployment: HardwareDeployment):
    return deployment.batteries, deployment.battery_register_map


@router.get("/data")
async def get_bms_data(hardware: Annotated[HardwareDeployment, Depends(get_hardware)]):
    try:
        # Update each unit
        batteries, register_map = get_batteries(hardware)
        for unit_id in batteries.iterate_slave_ids():
            # Assuming read_holding_registers returns a Dict[str, float]
            values = modbus_data_acquisition(batteries.hardware, register_map, slave_id=unit_id)
            filename = f"{BASE_DIR}/battery_{unit_id}.csv"
            trending_data = read_last_n_tail(filename, 8)
            trend = calculate_soc_trend(trending_data)
            current_soc = float(trending_data[-1]["Capacity"])
            time_to_go, soc_1hr, soc_2hr = calculate_charge_projections(current_soc, trend)
            trend_data = {
                "trend": trend,
                "time-to-go": time_to_go,
                "soc-1hr": soc_1hr,
                "soc-2hr": soc_2hr
            }
            if isinstance(values, dict):  # Ensure values is a dictionary
                await bms_store.update_unit_data(unit_id, values)
                await bms_store.add_unit_data(unit_id, trend_data)
            else:
                logger.error(f"Unexpected values type: {type(values)}")
        data = await bms_store.get_all_data()
        print(data)
        print('-----')

        # Now grab the trend data and calculate that fun!
        return JSONResponse(content={"data": data, "error": None})
    except Exception as e:
        logger.error(f"Error getting BMS data: {e}")
        return JSONResponse(content={"data": None, "error": str(e)})


@router.get("/historical/{unit_id}")
async def get_historical_data(unit_id: int, num_points: int = Query(default=4000, ge=100, le=10000)):
    try:
        # battery = batteries.get_definition(unit_id)
        filename = f"{BASE_DIR}/battery_{unit_id}.csv"
        last_points = deque(maxlen=num_points)
        with open(filename, 'r') as file:
            header = file.readline().strip()
            for line in file:
                last_points.append(line)

        csv_data = header + '\n' + '\n'.join(last_points)
        return JSONResponse(content={"data": csv_data, "error": None})
    except FileNotFoundError:
        logger.error(f"CSV file not found for unit {unit_id}")
        return JSONResponse(content={"data": None, "error": f"No historical data found for unit {unit_id}"})
    except Exception as e:
        logger.error(f"Error reading historical data for unit {unit_id}: {e}")
        return JSONResponse(content={"data": None, "error": str(e)})


@router.get("/modbus_register/{data}")
async def read_modbus_register(data: str, hardware: Annotated[HardwareDeployment, Depends(get_hardware)]):
    parsed_data = json.loads(data)
    unit_id = parsed_data['unit_id']
    m_map = ModbusMap.from_dict({"registers": [
        {
            "name": "ODQ",
            "data_type": parsed_data['type'],
            "address": parsed_data['register'],
            "units": "",
            "conversion_factor": 1.0,
            "description": "On demand query"
        }
    ]})
    batteries, _ = get_batteries(hardware)
    values = modbus_data_acquisition(batteries.hardware, m_map, slave_id=unit_id)
    # Handle the modbus read operation here
    return {"success": True, "value": values['ODQ']}


@router.get("/")
async def bms(request: Request, hardware: Annotated[HardwareDeployment, Depends(get_hardware)]):
    batteries, register_map = get_batteries(hardware)
    try:
        bms_data = await bms_store.get_all_data()
        return templates.TemplateResponse(
            "bms_v.html",
            {
                "batteries": batteries,
                "request": request,
                "bms_data": bms_data,
                "register_map": register_map,
                "error": None
            }
        )
    except Exception as e:
        logger.error(f"Error in BMS route: {e}")
        return templates.TemplateResponse(
            "bms_v.html",
            {
                "batteries": [],
                "request": request,
                "bms_data": {},
                "register_map": register_map,
                "error": str(e)
            }
        )
