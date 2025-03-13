import subprocess
from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from fastapi.responses import JSONResponse
from . import templates
import json
from typing import Annotated

from actions.action_factory import ActionFactory
from .hardware_deployment_route import HardwareDeploymentRoute, get_hardware
from utils import LogManager, run_command

logger = LogManager().get_logger(__name__)


router = APIRouter(prefix="/configuration", tags=["configuration"])


@router.get("/", name="configuration_index")
async def index(request: Request, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    git_branches = get_git_branches()
    current_branch = get_current_branch()
    return templates.TemplateResponse(
        "configuration.html",
        {
            "hardware": hardware,
            "request": request,
            "git_branches": git_branches,
            "current_branch": current_branch
        }
    )


# New route to handle firmware updates
@router.post("/update_firmware", name="update_firmware")
async def update_firmware(
        request: Request,
        branch: str = Form(...),
        action: str = Form(...)
):
    try:
        # Switch to the selected branch
        ActionFactory.execute_action("FirmwareUpdate", {"tag": branch}, None, None)

        # If the action is update_restart, restart the application
        if action == "update_restart":
            # Start application restart (this will depend on your setup)
            ActionFactory.execute_action("RestartApplication", params={}, None, None)

        # Return to the configuration page
        return RedirectResponse(url="/configuration", status_code=303)
    except Exception as e:
        # Handle errors
        return templates.TemplateResponse(
            "configuration.html",
            {
                "request": request,
                "error_message": f"Failed to update firmware: {str(e)}",
                "git_branches": get_git_branches(),
                "current_branch": get_current_branch()
            }
        )


@router.post("/ping/{section}")
async def ping_hardware(section: str, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        if section == "Actuators":
            manager = hardware.actuator_manager

            result = run_command(["ip", "-details", "link", "show", manager.channel], logger)
            return {"output": result.stdout if result.returncode == 0 else result.stderr}
        else:
            # Execute the ping command (limited to 2 pings for safety)
            result = run_command(["ping", "-c", "2", section], logger)
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
        logger.error(f"Error processing configuration file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing configuration file")


@router.get("/current/{section}")
async def get_current_configuration(section: str):
    if section not in configurations:
        raise HTTPException(status_code=400, detail="Invalid configuration section")

    if configurations[section] is None:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return JSONResponse(configurations[section])


# Helper functions to interact with git
def get_git_branches():
    """Get list of available git branches"""
    result = subprocess.run(
        ["git", "branch", "--list", "--all"],
        capture_output=True,
        text=True,
        check=True
    )

    branches = []
    for line in result.stdout.splitlines():
        # Clean branch names (remove asterisks and whitespace)
        branch = line.strip().replace("* ", "")
        # Remove remote prefixes if needed
        if branch.startswith("remotes/origin/"):
            branch = branch.replace("remotes/origin/", "")

        if branch and branch not in branches and not branch.startswith("HEAD"):
            branches.append(branch)

    return branches


def get_current_branch():
    """Get the name of the current git branch"""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()
