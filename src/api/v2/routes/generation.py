
from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from . import templates

from .hardware_deployment_route import HardwareDeploymentRoute, get_hardware
from bms_store import BMSDataStore

from utils import LogManager
logger = LogManager().get_logger("GenerationRoute")

router = APIRouter(prefix="/generation", tags=["generation"])
data_store = BMSDataStore()


@router.get("/")
async def index(request: Request, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        # Update each unit
        hardware = hardware.pv_cts
        if not hardware:
            return templates.TemplateResponse('hardware_not_configured.html',
                                              {"request": request,
                                               "hardware": "PV Generation CT's"})

        hardware.get_identifiers()
        logger.info(f"Got Inverter identifiers")
        data = await data_store.get_all_data()
        register_map = hardware.get_points("DATA")
        logger.info(f"GET inverters: {hardware.hardware_id}, devices: {len(hardware.devices)}")
        logger.info(f"DATA registers: {len(register_map)}")

        return templates.TemplateResponse(
            "generation.html",
            {
                "hardware": hardware,
                "request": request,
                "data": data,
                "register_map": register_map,
                "error": None
            }
        )
    except Exception as e:
        logger.error(f"{e}", exc_info=True)
        return templates.TemplateResponse(
            "generation.html",
            {
                "hardware": [],
                "request": request,
                "register_map": {},
                "error": str(e)
            }
        )


@router.get("/data")
async def get_test_data(hardware_def: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    cts = hardware_def.pv_cts
    if not cts:
        return JSONResponse(content={ "data": None, "error": "Not configured" })

    values = cts.hardware.test_device(cts.devices[0])
    return { "success": True, "value": values}
