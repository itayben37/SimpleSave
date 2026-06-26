from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.firebase import init_firebase
from app.config.settings import settings
from app.common.error_handlers import register_error_handlers
from app.modules.auth.router import router as auth_router
from app.modules.admin.router import router as admin_router
from app.modules.applications.router import router as applications_router
from app.modules.calculations.router import router as calculations_router
from app.modules.documents.router import router as documents_router
from app.modules.notifications.router import router as notifications_router
from app.modules.advisors.router import router as advisors_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In dev sanity-check mode we skip Firebase entirely, so the app can run
    # without valid Firebase credentials. (Production must have AUTH_BYPASS off.)
    if not (settings.auth_bypass and settings.environment != "production"):
        init_firebase()
    yield


app = FastAPI(
    title="SimpleSave API",
    description="Mortgage advisory platform API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
# applications_router and calculations_router already declare their own
# prefix ("/api/applications", "/api/calculations") on the APIRouter, so we must
# NOT pass prefix here or the path becomes "/api/applications/api/applications".
app.include_router(applications_router, tags=["applications"])
app.include_router(calculations_router, tags=["calculations"])
app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(notifications_router, prefix="/api/notifications", tags=["notifications"])
app.include_router(advisors_router, prefix="/api/advisors", tags=["advisors"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "simplesave-api"}
