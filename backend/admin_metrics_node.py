"""
GUIAME v1.5.11 — admin_metrics_node

Nodo de métricas administrativas para GUIAME.

Lee información real desde PostgreSQL:
- audit_logs
- users
- analyses

Objetivo:
- alimentar futuro dashboard administrador;
- mostrar actividad reciente;
- detectar errores y advertencias;
- medir uso del sistema;
- aprovechar la trazabilidad creada en v1.5.10.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import asyncpg


def _normalize_asyncpg_url(url: str) -> str:
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
           .replace("postgresql+psycopg2://", "postgresql://")
           .replace("postgresql+psycopg://", "postgresql://")
    )


def _get_database_url() -> str:
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

    except Exception:
        pass

    raise RuntimeError("No se pudo resolver DATABASE_URL para admin_metrics_node")


async def _table_exists(conn: asyncpg.Connection, table_name: str) -> bool:
    result = await conn.fetchval(
        "SELECT to_regclass($1) IS NOT NULL",
        f"public.{table_name}",
    )
    return bool(result)


async def _column_exists(
    conn: asyncpg.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    result = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = $1
              AND column_name = $2
        )
        """,
        table_name,
        column_name,
    )
    return bool(result)


async def _fetchval_safe(
    conn: asyncpg.Connection,
    query: str,
    *args: Any,
) -> Optional[Any]:
    try:
        return await conn.fetchval(query, *args)
    except Exception:
        return None


async def _fetch_safe(
    conn: asyncpg.Connection,
    query: str,
    *args: Any,
) -> List[Dict[str, Any]]:
    try:
        rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]
    except Exception:
        return []


async def get_admin_metrics(days: int = 7) -> Dict[str, Any]:
    """
    Devuelve métricas administrativas generales.

    days:
    período de análisis para eventos recientes.
    """
    if days < 1:
        days = 1

    if days > 90:
        days = 90

    since = datetime.now(timezone.utc) - timedelta(days=days)

    conn: Optional[asyncpg.Connection] = None

    metrics: Dict[str, Any] = {
        "version": "v1.5.11",
        "node": "admin_metrics_node",
        "period_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {},
        "events_by_type": [],
        "events_by_severity": [],
        "events_by_day": [],
        "top_endpoints": [],
        "recent_events": [],
        "warnings_and_errors": [],
        "tables": {},
    }

    try:
        conn = await asyncpg.connect(_get_database_url())

        audit_exists = await _table_exists(conn, "audit_logs")
        users_exists = await _table_exists(conn, "users")
        analyses_exists = await _table_exists(conn, "analyses")

        metrics["tables"] = {
            "audit_logs": audit_exists,
            "users": users_exists,
            "analyses": analyses_exists,
        }

        total_users = None
        total_analyses = None
        analyses_today = None
        rescue_cases_total = None

        if users_exists:
            total_users = await _fetchval_safe(
                conn,
                "SELECT COUNT(*) FROM users",
            )

        if analyses_exists:
            total_analyses = await _fetchval_safe(
                conn,
                "SELECT COUNT(*) FROM analyses",
            )

            if await _column_exists(conn, "analyses", "created_at"):
                analyses_today = await _fetchval_safe(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM analyses
                    WHERE created_at >= date_trunc('day', NOW())
                    """,
                )

            if await _column_exists(conn, "analyses", "rescue_case"):
                rescue_cases_total = await _fetchval_safe(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM analyses
                    WHERE rescue_case IS NOT NULL
                      AND rescue_case <> ''
                    """,
                )

        audit_events_total = None
        audit_events_today = None
        warnings_24h = None
        errors_24h = None

        if audit_exists:
            audit_events_total = await _fetchval_safe(
                conn,
                "SELECT COUNT(*) FROM audit_logs",
            )

            audit_events_today = await _fetchval_safe(
                conn,
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE created_at >= date_trunc('day', NOW())
                """,
            )

            warnings_24h = await _fetchval_safe(
                conn,
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE severity = 'warning'
                  AND created_at >= NOW() - INTERVAL '24 hours'
                """,
            )

            errors_24h = await _fetchval_safe(
                conn,
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE severity = 'error'
                  AND created_at >= NOW() - INTERVAL '24 hours'
                """,
            )

            metrics["events_by_type"] = await _fetch_safe(
                conn,
                """
                SELECT event_type, COUNT(*) AS total
                FROM audit_logs
                WHERE created_at >= $1
                GROUP BY event_type
                ORDER BY total DESC, event_type ASC
                """,
                since,
            )

            metrics["events_by_severity"] = await _fetch_safe(
                conn,
                """
                SELECT severity, COUNT(*) AS total
                FROM audit_logs
                WHERE created_at >= $1
                GROUP BY severity
                ORDER BY total DESC, severity ASC
                """,
                since,
            )

            metrics["events_by_day"] = await _fetch_safe(
                conn,
                """
                SELECT created_at::date AS day, COUNT(*) AS total
                FROM audit_logs
                WHERE created_at >= $1
                GROUP BY created_at::date
                ORDER BY day DESC
                """,
                since,
            )

            metrics["top_endpoints"] = await _fetch_safe(
                conn,
                """
                SELECT endpoint, COUNT(*) AS total
                FROM audit_logs
                WHERE created_at >= $1
                  AND endpoint IS NOT NULL
                GROUP BY endpoint
                ORDER BY total DESC, endpoint ASC
                LIMIT 10
                """,
                since,
            )

            metrics["recent_events"] = await _fetch_safe(
                conn,
                """
                SELECT
                    id,
                    event_type,
                    severity,
                    event_source,
                    endpoint,
                    method,
                    status_code,
                    created_at
                FROM audit_logs
                ORDER BY id DESC
                LIMIT 20
                """,
            )

            metrics["warnings_and_errors"] = await _fetch_safe(
                conn,
                """
                SELECT
                    id,
                    event_type,
                    severity,
                    event_source,
                    endpoint,
                    method,
                    status_code,
                    created_at
                FROM audit_logs
                WHERE severity IN ('warning', 'error')
                ORDER BY id DESC
                LIMIT 20
                """,
            )

        metrics["summary"] = {
            "total_users": total_users,
            "total_analyses": total_analyses,
            "analyses_today": analyses_today,
            "rescue_cases_total": rescue_cases_total,
            "audit_events_total": audit_events_total,
            "audit_events_today": audit_events_today,
            "warnings_24h": warnings_24h,
            "errors_24h": errors_24h,
        }

        return metrics

    finally:
        if conn is not None:
            await conn.close()
