import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.database import Base, engine
from backend.app.api.v1.router import api_v1_router
# Import models to ensure they are registered with metadata
import backend.app.models

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing HealthSupply Intelligence Modular Monolith...", extra={"props": {"env": settings.ENVIRONMENT}})
    # Create tables if not existing
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/initialized successfully.")
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")
    yield
    logger.info("Shutting down HealthSupply Intelligence Core.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured JSON request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
        extra={"props": {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": request.client.host if request.client else "unknown"
        }}
    )
    return response

# Root and Health check
@app.get("/health", tags=["system"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

# Mount /api/v1
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

dashboard_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../dashboard"))
if os.path.exists(dashboard_path):
    app.mount("/dashboard", StaticFiles(directory=dashboard_path, html=True), name="dashboard")

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/dashboard/")
