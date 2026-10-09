from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config


app = FastAPI(title="RLGym GUI backend", version=config.VERSION)

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

@app.get("/health", operation_id="getHealth", tags=["system"])
def health():
    return {"status": "ok"}

@app.get("/version", operation_id="getVersion", tags=["system"])
def version():
    return {"version": config.VERSION}