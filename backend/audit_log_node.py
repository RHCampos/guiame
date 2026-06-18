"""
GUIAME v1.5.10 — audit_log_node

Auditoría interna compatible con la estructura actual de GUIAME:
- FastAPI async
- SQLAlchemy/asyncpg
- PostgreSQL
- tabla audit_logs

El nodo está diseñado para no romper el flujo principal:
si falla la auditoría, la app sigue funcionando.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

import asyncpg


logger = logging.getLogger("guiame.audit_log_node")


def _normalize_asyncpg_url(url: str) -> str:
    """
    Convierte URLs tipo SQLAlchemy:
    postgresql+asyncpg://user:pass@host:port/db

    a formato asyncpg:
    postgresql://user:pass@host:port/db
    """
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
           .replace("postgresql+psycopg2://", "postgresql://")
           .replace("postgresql+psycopg://", "postgresql://")
    )


def _get_database_url() -> str:
    """
    Obtiene la URL de base de datos desde variables de entorno
    o desde guiame.db.database.
    """
    env_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("SQLALCHEMY_DATABASE_URL")
        or os.getenv("POSTGRES_URL")
    )

    if env_url:
        return _normalize_asyncpg_url(env_url)

    try:
        from guiame.db import database as db_database  # type: ignore

        for attr in (
            "DATABASE_URL",
            "SQLALCHEMY_DATABASE_URL",
            "POSTGRES_URL",
            "DATABASE_URI",
        ):
            value = getattr(db_database, attr, None)
            if value:
                return _normalize_asyncpg_url(str(value))

        engine = getattr(db_database, "engine", None)
        if engine is not None:
            url_obj = getattr(engine, "url", None)

            if url_obj is None and hasattr(engine, "sync_engine"):
                url_obj = getattr(engine.sync_engine, "url", None)

            if url_obj is not None:
                if hasattr(url_obj, "render_as_string"):
                    return _normalize_asyncpg_url(
                        url_obj.render_as_string(hide_password=False)
                    )
                return _normalize_asyncpg_url(str(url_obj))

    except Exception as exc:
        logger.warning("No se pudo leer guiame.db.database: %s", exc)

    raise RuntimeError("No se pudo resolver DATABASE_URL para audit_log_node")


def _safe_json(details: Optional[Dict[str, Any]]) -> str:
    try:
        return json.dumps(details or {}, ensure_ascii=False, default=str)
    except Exception:
        return "{}"


async def audit_log_async(
    *,
    event_type: str,
    user_id: Optional[int] = None,
    event_source: str = "backend",
    severity: str = "info",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    endpoint: Optional[str] = None,
    method: Optional[str] = None,
    status_code: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Inserta un evento en audit_logs usando asyncpg.
    Devuelve True si insertó correctamente.
    """
    conn = None

    try:
        database_url = _get_database_url()
        conn = await asyncpg.connect(database_url)

        await conn.execute(
            """
            INSERT INTO audit_logs (
                user_id,
                event_type,
                event_source,
                severity,
                ip_address,
                user_agent,
                endpoint,
                method,
                status_code,
                details
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10::jsonb
            )
            """,
            user_id,
            event_type[:80],
            event_source[:80],
            severity[:20],
            ip_address,
            user_agent,
            endpoint,
            method,
            status_code,
            _safe_json(details),
        )

        return True

    except Exception as exc:
        logger.warning("audit_log_node no pudo insertar evento: %s", exc)
        return False

    finally:
        try:
            if conn is not None:
                await conn.close()
        except Exception:
            pass


def audit_log(
    *,
    event_type: str,
    user_id: Optional[int] = None,
    event_source: str = "backend",
    severity: str = "info",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    endpoint: Optional[str] = None,
    method: Optional[str] = None,
    status_code: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Wrapper seguro para poder llamar auditoría desde código sync o async.

    - Si hay event loop activo, crea una tarea.
    - Si no hay event loop, ejecuta con asyncio.run.
    """
    kwargs = {
        "event_type": event_type,
        "user_id": user_id,
        "event_source": event_source,
        "severity": severity,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "details": details,
    }

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(audit_log_async(**kwargs))
    except RuntimeError:
        try:
            asyncio.run(audit_log_async(**kwargs))
        except Exception:
            pass
    except Exception:
        pass


def _client_ip_from_request(request) -> Optional[str]:
    try:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        if request.client:
            return request.client.host

    except Exception:
        return None

    return None


def event_type_from_http(method: str, path: str, status_code: int) -> str:
    path_lower = path.lower()

    if status_code >= 500:
        return "backend_error"

    if "/api/analyze" in path_lower:
        if status_code == 429:
            return "daily_limit_reached"
        if 200 <= status_code < 300:
            return "analysis_completed"
        return "analysis_failed"

    if "/api/rescue" in path_lower:
        if 200 <= status_code < 300:
            return "rescue_mode_used"
        return "rescue_mode_failed"

    if "/login" in path_lower or "/token" in path_lower:
        if 200 <= status_code < 300:
            return "login_success"
        return "login_failed"

    if "/register" in path_lower:
        if 200 <= status_code < 300:
            return "user_registered"
        return "user_register_failed"

    if "/reset" in path_lower or "/password" in path_lower:
        if 200 <= status_code < 300:
            return "password_event_success"
        return "password_event_failed"

    if status_code in (401, 403):
        return "unauthorized_access"

    return "api_request"


def severity_from_status(status_code: int) -> str:
    if status_code >= 500:
        return "error"
    if status_code in (401, 403, 429):
        return "warning"
    if status_code >= 400:
        return "warning"
    return "info"


def should_audit_path(path: str) -> bool:
    path_lower = path.lower()

    ignored_prefixes = (
        "/assets",
        "/static",
        "/favicon",
        "/robots.txt",
        "/health",
    )

    if path_lower.startswith(ignored_prefixes):
        return False

    return (
        path_lower.startswith("/api")
        or "login" in path_lower
        or "register" in path_lower
        or "password" in path_lower
        or "reset" in path_lower
    )


def audit_http_event(request, status_code: int) -> None:
    """
    Auditoría automática desde middleware FastAPI.
    """
    try:
        path = request.url.path
        method = request.method.upper()

        if not should_audit_path(path):
            return

        audit_log(
            event_type=event_type_from_http(method, path, status_code),
            event_source="http_middleware",
            severity=severity_from_status(status_code),
            ip_address=_client_ip_from_request(request),
            user_agent=request.headers.get("user-agent"),
            endpoint=path,
            method=method,
            status_code=status_code,
            details={
                "query_params": str(request.query_params) if request.query_params else "",
                "audit_version": "v1.5.10",
            },
        )

    except Exception:
        pass
