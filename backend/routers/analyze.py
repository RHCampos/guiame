import json
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
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
    # Extraer texto si es archivo
    content_to_analyze = data.content
    if data.input_type == "file":
        filename = data.filename if hasattr(data, "filename") else ""
        content_to_analyze = extract_text_from_file(data.content, filename)

    # Ejecutar el agente LangGraph
    result = await run_analysis(content_to_analyze, data.channel, data.input_type)

    # Preparar datos para guardar
    # Generar preview limpio según tipo
    if data.input_type == "file":
        ext = data.filename.split(".")[-1].upper() if "." in data.filename else "Archivo"
        content_preview = f"Archivo {ext}: {data.filename[:50]}" if data.filename else "Archivo adjunto"
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
    if data.rescue_case not in RESCUE_CASES:
        raise HTTPException(status_code=400, detail="Caso de rescate inválido")

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
