from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db.database import create_tables
from .routers import auth, analyze


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crear tablas al iniciar
    await create_tables()
    yield


app = FastAPI(
    title="GuIAme API",
    description="Agente Inteligente de Ciberseguridad para Usuarios No Expertos",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router,    prefix="/api")
app.include_router(analyze.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "GuIAme API", "version": "1.0.0"}

# ============================================================
# GUIAME v1.5.10 — audit_log_node
# Auditoría automática de endpoints relevantes.
# ============================================================
try:
    from guiame.audit_log_node import audit_http_event
except Exception:
    try:
        from backend.audit_log_node import audit_http_event
    except Exception:
        try:
            from audit_log_node import audit_http_event
        except Exception:
            audit_http_event = None


@app.middleware("http")
async def guiame_audit_log_middleware(request, call_next):
    response = await call_next(request)

    try:
        if audit_http_event is not None:
            audit_http_event(request, response.status_code)
    except Exception:
        pass

    return response

