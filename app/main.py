from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from threading import Thread

from app.src import schemas
from app.src.constants import API_TITLE, API_VERSION
from app.api.controller import app_executive, app_operator, app_vendor, app_public
from app.src.scheduler import trigger_schedules_worker


app = FastAPI(title=API_TITLE, version=API_VERSION)

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/executive", app_executive, "Executive API")
app.mount("/vendor", app_vendor, "Vendor API")
app.mount("/operator", app_operator, "Operator API")
app.mount("/public", app_public, "Public API")


# Health check endpoint
@app.get("/health", tags=["Health Check"], response_model=schemas.HealthStatus)
async def health_check():
    return {"status": "OK", "version": API_VERSION}


@app.on_event("startup")
def start_scheduler():
    """Start background scheduler worker."""
    thread = Thread(target=trigger_schedules_worker, daemon=True)
    thread.start()
