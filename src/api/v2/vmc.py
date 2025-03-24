from pathlib import Path
import subprocess
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from utils import LogManager
lm = LogManager("vmc.log")
logger = lm.get_logger("VMC")
lm.configure_library_loggers()
from routes import actuator, bms, configuration, analysis, inverters, modbus, system_status, generation
from api.v2.routes.hardware_deployment_route import HardwareDeploymentRoute


@asynccontextmanager
async def lifespan(fastapp: FastAPI):
    # Startup
    fastapp.state.hardware = HardwareDeploymentRoute()
    yield
    # Shutdown


# Initialize app with lifespan handler
def get_hardware_deployment() -> HardwareDeploymentRoute:
    return app.state.hardware


def get_git_version():
    try:
        return subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"]).decode().strip()
    except:
        return "V0.1.0"


BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Valexy Microcontroller System", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
logger.info("Created FastAPI app")

# Initialize templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["version"] = get_git_version()


# Include routers
app.include_router(actuator.router)
app.include_router(bms.router)
app.include_router(configuration.router)
app.include_router(analysis.router)
app.include_router(inverters.router)
app.include_router(modbus.router)
app.include_router(system_status.router)
app.include_router(generation.router)
logger.info(f"Loaded templates and routes.   Git version: {templates.env.globals['version']}")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
