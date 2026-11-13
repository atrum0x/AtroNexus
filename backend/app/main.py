from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from sqlalchemy import select

from app import auth
from app.capture import router as capture
from app.config import get_settings
from app.ifs import router as ifs
from app.internal import InternalKeyMiddleware
from app.db import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password


def seed_admin() -> None:
    settings = get_settings()
    if not settings.admin_username or not settings.admin_password:
        return
    with SessionLocal() as db:
        exists = db.scalar(select(User).where(User.username == settings.admin_username))
        if exists is None:
            db.add(
                User(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                )
            )
            db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
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
