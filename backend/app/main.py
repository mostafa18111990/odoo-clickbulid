from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import create_tables
from app.api.v1.endpoints import auth, instances, payments, bridge, domains


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title       = settings.APP_NAME,
    version     = settings.APP_VERSION,
    docs_url    = "/api/docs" if settings.DEBUG else None,
    redoc_url   = None,
    lifespan    = lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(auth.router,      prefix="/api/v1")
app.include_router(instances.router, prefix="/api/v1")
app.include_router(payments.router,  prefix="/api/v1")
app.include_router(bridge.router,    prefix="/api/v1")   # Odoo↔FastAPI bridge (apps, health)
app.include_router(domains.router,   prefix="/api/v1")   # Custom domain SSL automation


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
