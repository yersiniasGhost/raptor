from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse
from . import templates
import logging
from communications.modbus.modbus import modbus_data_acquisition
from bms_store import BMSDataStore, ModbusMap
from database.battery_deployment import BatteryDeployment

DATA_PATH = "/root/raptor/data"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/modbus", tags=["modbus"])

#
# @router.get("/modbus_register/{data}")
# async def get_register(request: Request):

# I can do this when i figure out how to pass in the ModbusHardware.
