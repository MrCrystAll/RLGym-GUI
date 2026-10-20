from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from app import config, configs, discovery, settings


# The operationId (and so the generated client method name) is the route function's name.
def operation_id(route: APIRoute) -> str:
    return route.name


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    discovery.stop_worker()                              # don't leave the user's Python running


app = FastAPI(
    title="RLGym GUI backend",
    version=config.VERSION,
    generate_unique_id_function=operation_id,
    lifespan=lifespan,
)

@app.middleware("http")
async def check_token(request, call_next):
    if request.method != "OPTIONS" and request.headers.get("x-api-token") != config.TOKEN:
        return JSONResponse({"detail": "Invalid token"}, status_code=401)
    return await call_next(request)

# Needed in dev (Angular on :4200). In production, the page loads from file://,
# whose origin is "null", so allow that too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "null"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Health(BaseModel):
    status: str


class Version(BaseModel):
    version: str


@app.get("/health", tags=["system"])
def get_health() -> Health:
    return Health(status="ok")

@app.get("/version", tags=["system"])
def get_version() -> Version:
    return Version(version=config.VERSION)


app.include_router(settings.router)
app.include_router(discovery.router)
app.include_router(configs.router)
