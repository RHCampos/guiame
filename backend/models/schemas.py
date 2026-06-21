from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


# ── AUTH ──────────────────────────────────────────
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    credential: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str
    user_email: str

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime
    input_type: str = "msg"
    rescue_case: Optional[str] = None
    rescue_level: Optional[str] = None
    rescue_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── ANÁLISIS ──────────────────────────────────────
class AnalyzeRequest(BaseModel):
    content: str          # Texto del mensaje, URL o descripción
    filename: str = ""    # Nombre del archivo (para detectar tipo)
    channel: str = "otro" # whatsapp | sms | email | telegram | redes | otro
    input_type: str = "msg" # msg | url | file

class SignalItem(BaseModel):
    msg: str
    severity: str  # danger | warn

class AnalyzeResponse(BaseModel):
    analysis_id: int
    level: str              # danger | warn | safe
    score: int              # 0-100
    confidence: int         # 0-100
    title: str
    subtitle: str
    explanation: str        # Explicación en lenguaje claro (XAI)
    signals: list[SignalItem]
    recommendations: list[str]
    similar_cases: int      # Cuántos casos similares encontró el RAG


# ── HISTORIAL ─────────────────────────────────────
class HistoryItem(BaseModel):
    id: int
    content_preview: str
    channel: str
    level: str
    score: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── MODO RESCATE ───────────────────────────────────
class RescueRequest(BaseModel):
    analysis_id: int
    rescue_case: str


# ── FEEDBACK ──────────────────────────────────────
class FeedbackRequest(BaseModel):
    analysis_id: int
    is_correct: bool        # True = el resultado fue correcto
    comment: Optional[str] = None
