from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from . import templates
import json
from typing import Dict, Optional
import logging
from .system_configuration import SystemConfiguration


router = APIRouter(prefix="/configuration", tags=["configuration"])

# Dictionary to store the current configurations
configurations: Dict[str, dict] = {
    "actuator": None,
    "bms": None,
    "inverter": None,
    "generation": None
}


# Create a global instance of SystemConfiguration
system_config = SystemConfiguration()


@router.get("/", name="configuration_index")
async def index(request: Request):
    return templates.TemplateResponse(
        "configuration.html",
        {"request": request}
    )


@router.post("/upload/{section}")
async def upload_configuration(
        section: str,
        file: UploadFile = File(...),
):
    if section not in configurations:
        raise HTTPException(status_code=400, detail="Invalid configuration section")

    try:
        content = await file.read()
        config_data = json.loads(content.decode())

        # Update both the configurations dictionary and SystemConfiguration instance
        configurations[section] = config_data
        system_config.update_config(section, config_data)

        return JSONResponse({
            "status": "success",
            "message": f"{section} configuration updated successfully",
            "config": config_data
        })
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        logging.error(f"Error processing configuration file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing configuration file")


@router.get("/current/{section}")
async def get_current_configuration(section: str):
    if section not in configurations:
        raise HTTPException(status_code=400, detail="Invalid configuration section")

    if configurations[section] is None:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return JSONResponse(configurations[section])