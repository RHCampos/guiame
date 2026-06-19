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


# ============================================================
# GUIAME v1.5.11 — admin_metrics_node
# Endpoint interno protegido para métricas administrativas.
# ============================================================
try:
    import hmac
    import os
    from typing import Optional

    from fastapi import Header, HTTPException, Query

    from guiame.admin_metrics_node import get_admin_metrics

    def _guiame_admin_metrics_expected_token() -> Optional[str]:
        token = os.getenv("GUIAME_ADMIN_METRICS_TOKEN")

        if token:
            return token.strip()

        local_paths = (
            "/app/guiame/admin_metrics_token.local",
            "backend/admin_metrics_token.local",
            "admin_metrics_token.local",
        )

        for path in local_paths:
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        value = f.read().strip()
                        if value:
                            return value
            except Exception:
                pass

        return None


    @app.get("/api/admin/metrics")
    async def guiame_admin_metrics_endpoint(
        days: int = Query(7, ge=1, le=90),
        x_guiame_admin_token: Optional[str] = Header(default=None),
    ):
        expected_token = _guiame_admin_metrics_expected_token()

        if not expected_token:
            raise HTTPException(
                status_code=503,
                detail="Admin metrics token is not configured",
            )

        if not x_guiame_admin_token or not hmac.compare_digest(
            x_guiame_admin_token,
            expected_token,
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid admin metrics token",
            )

        return await get_admin_metrics(days=days)

except Exception as exc:
    print(f"GUIAME v1.5.11 admin_metrics_node no pudo cargarse: {exc}")

