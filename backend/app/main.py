from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app import auth, migrate
from app.accounts import seed_platform_admin
from app.capture import router as capture
from app.config import get_settings
from app.ifs import router as ifs
from app.db import SessionLocal
from app.internal import InternalKeyMiddleware


def seed_admin() -> None:
    settings = get_settings()
    if not settings.admin_username or not settings.admin_password:
        return
    with SessionLocal() as db:
        seed_platform_admin(db, settings.admin_username, settings.admin_password, settings.admin_email)


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate.upgrade()
    seed_admin()
    yield


def operation_id(route: APIRoute) -> str:
    # The frontend's generated client (Orval) names its functions after these,
    # so use the handler name ("login") instead of FastAPI's default
    # ("login_api_auth_login_post"). Handler names must be unique.
    return route.name


app = FastAPI(title="AtroNexus API", lifespan=lifespan, generate_unique_id_function=operation_id)

app.add_middleware(InternalKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ifs.router)
app.include_router(capture.router)
app.include_router(capture.public_router)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
