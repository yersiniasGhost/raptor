from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File
from fastapi.responses import JSONResponse
import subprocess
from . import templates
import json
from typing import Dict, Annotated
import logging
from .hardware_deployment import HardwareDeployment, get_hardware


router = APIRouter(prefix="/configuration", tags=["configuration"])


@router.get("/", name="configuration_index")
async def index(request: Request, hardware: Annotated[HardwareDeployment, Depends(get_hardware)]):
    return templates.TemplateResponse(
        "configuration.html",
        {
            "hardware": hardware,
            "request": request
        }
    )


@router.post("/ping/{section}")
async def ping_hardware(section: str, hardware: Annotated[HardwareDeployment, Depends(get_hardware)]):
    try:
        if section == "Actuators":
            manager = hardware.actuator_manager

            result = subprocess.run(["ip", "-details", "link", "show", manager.channel], capture_output=True, text=True)
            return {"output": result.stdout if result.returncode == 0 else result.stderr}
        else:
            # Execute the ping command (limited to 2 pings for safety)
            result = subprocess.run(["ping", "-c", "2", section], capture_output=True, text=True)
            return {"output": result.stdout if result.returncode == 0 else result.stderr}
    except Exception as e:
        return {"error": str(e)}


@router.post("/upload/{section}")
async def upload_configuration(section: str, file: UploadFile = File(...),):

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