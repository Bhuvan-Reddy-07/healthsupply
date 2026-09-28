from fastapi import APIRouter
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.facilities import router as facilities_router
from backend.app.api.v1.items import router as items_router
from backend.app.api.v1.inventory import router as inventory_router
from backend.app.api.v1.transactions import router as transactions_router
from backend.app.api.v1.forecasts import router as forecasts_router
from backend.app.api.v1.alerts import router as alerts_router
from backend.app.api.v1.transfers import router as transfers_router
from backend.app.api.v1.audit import router as audit_router
from backend.app.api.v1.simulator import router as simulator_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(facilities_router)
api_v1_router.include_router(items_router)
api_v1_router.include_router(inventory_router)
api_v1_router.include_router(transactions_router)
api_v1_router.include_router(forecasts_router)
api_v1_router.include_router(alerts_router)
api_v1_router.include_router(transfers_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(simulator_router)
