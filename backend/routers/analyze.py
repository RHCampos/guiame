import json
import hashlib
import ipaddress
import socket
import re
from urllib.parse import urlparse
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from jose import jwt, JWTError

from ..db.database import get_db, User, Analysis, Feedback
from ..models.schemas import (
    AnalyzeRequest, AnalyzeResponse, SignalItem,
    HistoryItem, FeedbackRequest, RescueRequest
)
from ..agent.graph import run_analysis
from ..agent.file_extractor import extract_text_from_file
from ..config import settings

router = APIRouter(tags=["analysis"])
bearer = HTTPBearer()

DAILY_ANALYSIS_LIMIT = 10


ALLOWED_CHANNELS = {
    "whatsapp",
    "sms",
    "email",
    "telegram",
    "redes",
    "otro",
}

MAX_MESSAGE_CHARS = 10000
MAX_FEEDBACK_COMMENT_CHARS = 1000
MAX_HISTORY_LIMIT = 50


def validate_channel_or_raise(channel: str) -> str:
    clean = str(channel or "otro").strip().lower()

    if clean not in ALLOWED_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail="Canal inválido"
        )

    return clean


def validate_content_or_raise(input_type: str, content: str) -> None:
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(
            status_code=400,
            detail="Contenido vacío o inválido"
        )

    if input_type == "msg" and len(content) > MAX_MESSAGE_CHARS:
        raise HTTPException(
            status_code=400,
            detail="El mensaje supera el tamaño máximo permitido"
        )


def validate_positive_id_or_raise(value: int, label: str = "ID") -> None:
    try:
        numeric_value = int(value)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"{label} inválido"
        )

    if numeric_value <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"{label} inválido"
        )


def validate_feedback_comment_or_raise(comment: str | None) -> str | None:
    if comment is None:
        return None

    clean = str(comment).strip()

    if len(clean) > MAX_FEEDBACK_COMMENT_CHARS:
        raise HTTPException(
            status_code=400,
            detail="El comentario supera el tamaño máximo permitido"
        )

    return clean or None


MAX_FILE_BYTES = 10 * 1024 * 1024

ALLOWED_FILE_EXTS = {
    "txt", "csv", "json", "md", "log", "eml",
    "pdf", "docx",
    "png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff",
}

BLOCKED_FILE_EXTS = {
    "exe", "bat", "cmd", "com", "msi", "scr", "pif", "dll", "sys",
    "jar", "ps1", "vbs", "vbe", "js", "jse", "wsf", "wsh",
    "html", "htm", "svg", "php", "asp", "aspx", "jsp",
    "docm", "xlsm", "pptm", "lnk", "iso", "apk",
}


def safe_filename(filename: str) -> str:
    name = str(filename or "").replace("\\", "/").split("/")[-1].strip()
    name = re.sub(r"[^A-Za-z0-9._()\- áéíóúÁÉÍÓÚñÑ]", "_", name)
    return name[:120]


def get_file_ext(filename: str) -> str:
    name = safe_filename(filename).lower()
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1]


def estimate_payload_size_bytes(content: str) -> int:
    raw = str(content or "").strip()

    if raw.lower().startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]

    compact = re.sub(r"\s+", "", raw)

    # Si parece base64, estimamos tamaño decodificado.
    if compact and re.fullmatch(r"[A-Za-z0-9+/=_-]+", compact):
        return int(len(compact) * 3 / 4)

    return len(raw.encode("utf-8", errors="ignore"))


def validate_file_input_or_raise(content: str, filename: str) -> str:
    clean_name = safe_filename(filename)
    ext = get_file_ext(clean_name)

    if not clean_name or not ext:
        raise HTTPException(
            status_code=400,
            detail="Archivo no permitido"
        )

    if ext in BLOCKED_FILE_EXTS or ext not in ALLOWED_FILE_EXTS:
        raise HTTPException(
            status_code=400,
            detail="Tipo de archivo no permitido por seguridad"
        )

    if not isinstance(content, str) or not content.strip():
        raise HTTPException(
            status_code=400,
            detail="Archivo vacío o inválido"
        )

    if estimate_payload_size_bytes(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Archivo demasiado grande"
        )

    return clean_name


def _is_blocked_ip(ip_obj: ipaddress._BaseAddress) -> bool:
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    )


def is_safe_public_url(raw_url: str) -> bool:
    """
    Valida URLs públicas para evitar esquemas peligrosos y destinos internos.
    Bloquea javascript:, data:, file:, localhost, loopback, redes privadas y rangos no públicos.
    """
    if not raw_url:
        return False

    raw_url = raw_url.strip()

    if len(raw_url) > 2048:
        return False

    parsed = urlparse(raw_url)

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname

    if not hostname:
        return False

    hostname = hostname.lower().strip("[]")

    blocked_hosts = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
    }

    if hostname in blocked_hosts:
        return False

    # Si el host ya es una IP literal, validarla directamente
    try:
        ip_obj = ipaddress.ip_address(hostname)
        if _is_blocked_ip(ip_obj):
            return False
    except ValueError:
        pass

    # Resolver DNS y bloquear si apunta a una red interna/no pública
    try:
        addr_infos = socket.getaddrinfo(hostname, None)

        for info in addr_infos:
            resolved_ip = info[4][0]
            ip_obj = ipaddress.ip_address(resolved_ip)

            if _is_blocked_ip(ip_obj):
                return False
    except Exception:
        return False

    return True


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    data: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validación general del tipo de entrada
    if data.input_type not in {"msg", "url", "file"}:
        raise HTTPException(
            status_code=400,
            detail="Tipo de entrada inválido"
        )

    # Validaciones de backend para entrada general
    data.channel = validate_channel_or_raise(data.channel)
    validate_content_or_raise(data.input_type, data.content)

    # Validación de seguridad para URLs antes de consumir cuota o ejecutar el agente
    if data.input_type == "url":
        if not is_safe_public_url(data.content):
            raise HTTPException(
                status_code=400,
                detail="URL inválida o no permitida"
            )

    # Validación de seguridad para archivos antes de consumir cuota o ejecutar el agente
    safe_file_name = ""
    if data.input_type == "file":
        safe_file_name = validate_file_input_or_raise(data.content, data.filename)

    # Control de uso diario por usuario
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    daily_count_result = await db.execute(
        select(func.count(Analysis.id)).where(
            Analysis.user_id == current_user.id,
            Analysis.created_at >= today_start
        )
    )
    used_today = daily_count_result.scalar() or 0

    if used_today >= DAILY_ANALYSIS_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Alcanzaste el límite diario de 10 análisis. Podrás volver a consultar mañana.",
                "code": "DAILY_LIMIT_REACHED",
                "limit": DAILY_ANALYSIS_LIMIT,
                "used_today": used_today
            }
        )

    # Extraer texto si es archivo
    content_to_analyze = data.content
    if data.input_type == "file":
        filename = safe_file_name or safe_filename(data.filename if hasattr(data, "filename") else "")
        content_to_analyze = extract_text_from_file(data.content, filename)

    # Ejecutar el agente LangGraph
    result = await run_analysis(content_to_analyze, data.channel, data.input_type)

    # Preparar datos para guardar
    # Generar preview limpio según tipo
    if data.input_type == "file":
        filename = safe_file_name or safe_filename(data.filename)
        ext = filename.split(".")[-1].upper() if "." in filename else "Archivo"
        content_preview = f"Archivo {ext}: {filename[:50]}" if filename else "Archivo adjunto"
    elif data.input_type == "url":
        content_preview = data.content[:80]
    else:
        # Mensaje: limpiar y truncar
        clean = data.content.replace("\n", " ").replace("\r", " ").strip()
        content_preview = clean[:80]
    content_hash = hashlib.sha256(data.content.encode()).hexdigest()
    signals_json = json.dumps(result["heuristic_hits"], ensure_ascii=False)
    recs_json = json.dumps(result["llm_recommendations"], ensure_ascii=False)

    # Guardar análisis en DB
    analysis = Analysis(
        user_id=current_user.id,
        content_preview=content_preview,
        content_hash=content_hash,
        channel=data.channel,
        input_type=data.input_type,
        level=result["final_level"],
        score=result["final_score"],
        confidence=result["final_confidence"],
        explanation=result["llm_explanation"],
        signals=signals_json,
        recommendations=recs_json,
    )
    # Generar y guardar embedding
    try:
        import voyageai
        from sqlalchemy import text
        vo = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
        emb_result = vo.embed([content_to_analyze[:2000]], model="voyage-large-2")
        embedding = emb_result.embeddings[0]
        analysis.embedding = embedding
    except Exception:
        pass
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    # Construir respuesta
    level = result["final_level"]
    titles = {
        "danger": "¡Cuidado! Parece una estafa",
        "warn":   "Mensaje sospechoso",
        "safe":   "Parece seguro",
    }
    subtitles = {
        "danger": "Este mensaje tiene señales de phishing o fraude",
        "warn":   "Tiene señales de alerta. Procedé con precaución",
        "safe":   "No encontramos señales de alarma",
    }

    signals = [
        SignalItem(msg=h["msg"], severity=h["severity"])
        for h in result["heuristic_hits"]
    ]

    return AnalyzeResponse(
        analysis_id=analysis.id,
        level=level,
        score=result["final_score"],
        confidence=result["final_confidence"],
        title=titles[level],
        subtitle=subtitles[level],
        explanation=result["llm_explanation"],
        signals=signals,
        recommendations=result["llm_recommendations"],
        similar_cases=result["rag_similar_cases"],
    )


@router.get("/history", response_model=list[HistoryItem])
async def get_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if limit < 1:
        limit = 1
    if limit > MAX_HISTORY_LIMIT:
        limit = MAX_HISTORY_LIMIT

    result = await db.execute(
        select(Analysis)
        .where(Analysis.user_id == current_user.id)
        .order_by(desc(Analysis.created_at))
        .limit(limit)
    )
    analyses = result.scalars().all()
    return [
        HistoryItem(
            id=a.id,
            content_preview=a.content_preview,
            channel=a.channel,
            level=a.level,
            score=a.score,
            created_at=a.created_at,
        )
        for a in analyses
    ]


RESCUE_CASES = {
    "no_click": {"level": "preventivo", "label": "No hizo clic"},
    "clicked_link": {"level": "atencion", "label": "Hizo clic en el enlace"},
    "entered_password": {"level": "urgente", "label": "Ingresó una contraseña"},
    "bank_data": {"level": "critico", "label": "Ingresó datos bancarios"},
    "shared_code": {"level": "critico", "label": "Compartió un código de verificación"},
    "opened_file": {"level": "urgente", "label": "Descargó o abrió un archivo"},
}


@router.post("/rescue", status_code=200)
async def save_rescue_case(
    data: RescueRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    validate_positive_id_or_raise(data.analysis_id, "Análisis")

    if data.rescue_case not in RESCUE_CASES:
        raise HTTPException(status_code=400, detail="Caso de rescate inválido")

    validate_positive_id_or_raise(data.analysis_id, "Análisis")
    data.comment = validate_feedback_comment_or_raise(data.comment)

    result = await db.execute(
        select(Analysis).where(
            Analysis.id == data.analysis_id,
            Analysis.user_id == current_user.id
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")

    analysis.rescue_case = data.rescue_case
    analysis.rescue_level = RESCUE_CASES[data.rescue_case]["level"]
    analysis.rescue_used_at = datetime.utcnow()

    await db.commit()

    return {
        "message": "Modo Rescate registrado correctamente",
        "analysis_id": analysis.id,
        "rescue_case": analysis.rescue_case,
        "rescue_level": analysis.rescue_level
    }



@router.post("/feedback", status_code=200)
async def submit_feedback(
    data: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verificar que el análisis existe y pertenece al usuario
    result = await db.execute(
        select(Analysis).where(
            Analysis.id == data.analysis_id,
            Analysis.user_id == current_user.id
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")

    feedback = Feedback(
        analysis_id=data.analysis_id,
        user_id=current_user.id,
        is_correct=data.is_correct,
        comment=data.comment,
    )
    db.add(feedback)
    await db.commit()

    return {"message": "Feedback registrado. ¡Gracias por ayudarnos a mejorar!"}
