import subprocess
from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from fastapi.responses import JSONResponse
from . import templates
import json
from typing import Annotated

from database.db_utils import get_mqtt_config
from config.mqtt_config import MQTTConfig
from actions.action_factory import ActionFactory
from .hardware_deployment_route import HardwareDeploymentRoute, get_hardware
from utils import LogManager, get_mac_address
from cloud.mqtt_comms import check_connection

logger = LogManager().get_logger(__name__)


router = APIRouter(prefix="/configuration", tags=["configuration"])


@router.post("/mqtt-test", name="mqtt-test")
async def mqtt_test(request: Request, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    mqtt_broker: MQTTConfig = get_mqtt_config(logger)
    status = await check_connection(mqtt_broker, logger)
    return status


@router.get("/", name="configuration_index")
async def index(request: Request, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    git_branches = get_git_branches()
    current_branch = get_current_branch()
    mqtt_broker: MQTTConfig = get_mqtt_config(logger)
    mac_address = get_mac_address()
    return templates.TemplateResponse(
        "configuration.html",
        {
            "hardware": hardware,
            "request": request,
            "git_branches": git_branches,
            "current_branch": current_branch,
            "mqtt_broker_ip": mqtt_broker.broker,
            "mqtt_broker_port": mqtt_broker.port,
            "mqtt_path": mqtt_broker.client_id,
            "mac_address": mac_address
        }
    )


@router.post("/service/{action}", name="service-action")
async def service_action(action: str, service_data: dict):
    service = service_data.get("service")
    logger.info(f"Requested {action} of service {service}")

    # Validate action
    if action not in ["status", "restart", "stop", "tail"]:
        return {"error": f"Invalid action: {action}"}

    # Validate service
    # if service not in ["vmc-ui", "cmd-controller", "iot-controller", "reverse-tunnel"]:
    #     return {"error": f"Invalid service: {service}"}

    if action == "tail":
        status, cmd_response = await ActionFactory.execute_action("tail_log", {"lines": 25, "process": service}, None, None)
        rs = cmd_response.get("results", {})
        txt = rs.get("output", "NA")
    else:
        # Execute the appropriate action based on the parameters
        status, cmd_response = await ActionFactory.execute_action("systemctl",
                                                              {"cmd": action, "target": service}, None, None)
        rs = cmd_response.get("results", {})
        txta = rs.get(service, {})
        txt = txta.get("output", "NA")

    result = {"status": status, "response": cmd_response}
    return {"output": result, "txt": txt}


@router.post("/recommission", name="recommission")
async def recommission(request: Request):
    logger.info("Requested to recommission VMC")
    try:
        # Switch to the selected branch
        await ActionFactory.execute_action("recommission", {}, None, None)
        # await ActionFactory.execute_action("restart", {}, None, None)

    except Exception as e:
        # Handle errors
        return templates.TemplateResponse(
            "configuration.html",
            {
                "request": request,
                "error_message": f"Failed to recommission system: {str(e)}",
                "git_branches": get_git_branches(),
                "current_branch": get_current_branch()
            }
        )


@router.post("/reconfigure", name="reconfigure")
async def reconfigure(request: Request):
    logger.info("Requested to reconfigure VMC")
    try:
        # Switch to the selected branch
        await ActionFactory.execute_action("reconfigure", {}, None, None)
        await ActionFactory.execute_action("restart",{"skip_reverse_tunnel": True}, None, None)

    except Exception as e:
        # Handle errors
        return templates.TemplateResponse(
            "configuration.html",
            {
                "request": request,
                "error_message": f"Failed to reconfigure system: {str(e)}",
                "git_branches": get_git_branches(),
                "current_branch": get_current_branch()
            }
        )


# Route to handle firmware updates
@router.post("/update_firmware", name="update_firmware")
async def update_firmware(
        request: Request,
        branch: str = Form(...),
        action: str = Form(...)
):
    try:
        # Switch to the selected branch
        await ActionFactory.execute_action("firmware_update", {"tag": branch}, None, None)

        # If the action is update_restart, restart the application
        if action == "update_restart":
            await ActionFactory.execute_action("restart", {"skip_reverse_tunnel": True}, None, None)

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


@router.post("/diagnose/{section}")
async def diagnose_hardware(section: str, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        return {"output": "Diagnose Hardware TBD", "status": "OK"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/test_alarms/{section}")
async def alarms_hardware(section: str, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        device = hardware.get_hardware(section)
        if device:
            result, status = device.alarm_checks()
            return {"output": result, "status": status}
        return {"output": "No device found for Alarm checks", "status": "OK"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/ping/{section}")
async def ping_hardware(section: str, hardware: Annotated[HardwareDeploymentRoute, Depends(get_hardware)]):
    try:
        device = hardware.get_hardware(section)
        if device:
            result, status = device.ping_hardware()
            return {"output": result, "status": status}
        else:
            return {"output":  "No devices found", "status": False}

    #     if section == "Actuators":
    #         device = hardware.actuator_manager
    #
    #         result, status = manager.ping_hardware()
    #         return
    #     elif section == "BMS":
    #         bms = hardware.batteries
    #         result, status = hardware.batteries.ping_hardware()
    #         return {"output": result, "status": status}
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
def get_git_branches_orig():
    """Get list of available git branches"""
    # fetch first?
    subprocess.run(["git", "remote", "update", "origin", "--prune"])
    result = subprocess.run(
        ["git", "branch", "--list", "--all"],
        capture_output=True,
        text=True,
        check=True
    )
    logger.info(f"git branch --list --all  returns: {result}")

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


def get_git_branches():
    """Get list of available git branches without fetching content"""
    result = subprocess.run(
        ["git", "ls-remote", "--heads", "origin"],
        capture_output=True,
        text=True,
        check=True
    )
    logger.info(f"git ls-remote --heads origin returns: {result}")

    branches = []
    for line in result.stdout.splitlines():
        # Each line has format: "commit_hash refs/heads/branch_name"
        if not line.strip():
            continue

        parts = line.split()
        if len(parts) >= 2:
            # Extract branch name from refs/heads/branch_name
            branch = parts[1].replace("refs/heads/", "")
            if branch and branch not in branches and not branch == "HEAD":
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
