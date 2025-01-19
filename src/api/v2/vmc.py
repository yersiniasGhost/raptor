from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from routes import actuator, bms

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown

# Initialize app with lifespan handler
app = FastAPI(title="Valexy Microcontroller System", lifespan=lifespan)

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(actuator.router)
app.include_router(bms.router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
