from pathlib import Path
import subprocess
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from utils import LogManager, EnvVars
from database.database_manager import DatabaseManager
from api.v2.auth import (
    AuthenticationMiddleware, verify_password,
    create_session, destroy_session, is_password_set
)


lm = LogManager("vmc-ui.log")
logger = lm.get_logger("VMC")
lm.configure_library_loggers()
from routes import (actuator, bms, configuration, analysis, inverters,
                    modbus, system_status, generation, charge_controller)
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


def reset_hardware_deployment() -> HardwareDeploymentRoute:
    app.state.hardware = HardwareDeploymentRoute()
    return app.state.hardware


def get_git_version():
    try:
        return subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"]).decode().strip()
    except:
        return "V0.1.0"


BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Valexy Microcontroller System", lifespan=lifespan)

# Add authentication middleware
app.add_middleware(AuthenticationMiddleware)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
logger.info("Created FastAPI app")

# Initialize templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
# templates.env.globals["version"] = get_git_version()
raptor_data = DatabaseManager().get_raptor()
templates.env.globals["raptor_header"] = (raptor_data or {}).get('name', "Not configured")
templates.env.globals["auth_enabled"] = is_password_set()


# Include routers
app.include_router(actuator.router)
app.include_router(bms.router)
app.include_router(configuration.router)
app.include_router(analysis.router)
app.include_router(inverters.router)
app.include_router(modbus.router)
app.include_router(system_status.router)
app.include_router(generation.router)
app.include_router(charge_controller.router)
# logger.info(f"Loaded templates and routes.   Git version: {templates.env.globals['version']}")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page"""
    raptor_data = DatabaseManager().get_raptor()
    raptor_name = (raptor_data or {}).get('name', '')
    return templates.TemplateResponse("login.html", {
        "request": request,
        "raptor_name": raptor_name
    })


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    """Handle login form submission"""
    raptor_data = DatabaseManager().get_raptor()
    raptor_name = (raptor_data or {}).get('name', '')

    if verify_password(password):
        # Create session
        session_token = create_session(request)
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_token", value=session_token, httponly=True, max_age=86400)
        logger.info("User logged in successfully")
        return response
    else:
        logger.warning("Failed login attempt")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid password",
            "raptor_name": raptor_name
        }, status_code=401)


@app.get("/logout")
async def logout(request: Request):
    """Handle logout"""
    destroy_session(request)

    # If no password is set, redirect to home instead of login
    redirect_url = "/login" if is_password_set() else "/"
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.delete_cookie(key="session_token")
    logger.info("User logged out")
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
