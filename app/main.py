from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.src import schemas
from app.src.constants import API_TITLE, API_VERSION
from app.api.controller import app_executive, app_operator, app_vendor
from app.api.controller import app_public


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
