import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt
import bcrypt as _bcrypt
import httpx
from ..db.database import get_db, User
from ..models.schemas import RegisterRequest, LoginRequest, TokenResponse, GoogleLoginRequest, ForgotPasswordRequest, ResetPasswordRequest, ForgotPasswordRequest, ResetPasswordRequest
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES_1 = 15    # 1er bloqueo
LOCKOUT_MINUTES_2 = 60    # 2do bloqueo
LOCKOUT_PERMANENT = 3     # A partir del 3er bloqueo → forzar reset
VERIFICATION_EXPIRE_HOURS = 24

# --- Passwords ---
def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password[:72].encode(), _bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain[:72].encode(), hashed.encode())

# --- JWT ---
def create_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

# --- Email de verificación ---
async def send_verification_email(email: str, name: str, token: str):
    verify_url = f"https://guiame.pro/verify.html?token={token}"
    html = f"""
    <div style="font-family: 'DM Sans', Arial, sans-serif; background:#080b12; color:#f0f4ff; padding:40px; max-width:520px; margin:auto; border-radius:12px;">
      <div style="text-align:center; margin-bottom:24px;">
        <span style="font-family:Rajdhani,sans-serif; font-size:32px;">
          <span style="color:#f97316">Gu</span><span style="color:#60a5fa">IA</span><span style="color:#f97316">me</span>
        </span>
      </div>
      <h2 style="color:#f0f4ff; margin-bottom:8px;">Hola, {name} 👋</h2>
      <p style="color:#94a3c0;">Gracias por registrarte en GuIAme. Para activar tu cuenta hacé clic en el botón:</p>
      <div style="text-align:center; margin:32px 0;">
        <a href="{verify_url}" style="background:#f97316; color:#fff; padding:14px 32px; border-radius:8px; text-decoration:none; font-weight:600; font-size:16px;">
          Verificar mi cuenta
        </a>
      </div>
      <p style="color:#94a3c0; font-size:13px;">Este link expira en 24 horas. Si no creaste una cuenta, ignorá este mensaje.</p>
      <hr style="border-color:#1a2236; margin:24px 0;">
      <p style="color:#94a3c0; font-size:12px; text-align:center;">© 2026 GuIAme · Asistente Inteligente de Ciberseguridad</p>
    </div>
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": "GuIAme <noreply@guiame.pro>",
                "to": [email],
                "subject": "Verificá tu cuenta de GuIAme",
                "html": html,
            },
        )
        if resp.status_code not in (200, 201):
            raise HTTPException(status_code=500, detail="No se pudo enviar el email de verificación")

# --- Endpoints ---
@router.post("/register", status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    if len(data.password) < 12:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 12 caracteres")

    token = secrets.token_hex(32)
    expires = datetime.utcnow() + timedelta(hours=VERIFICATION_EXPIRE_HOURS)

    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        is_verified=False,
        verification_token=token,
        verification_token_expires=expires,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await send_verification_email(data.email, data.name, token)

    return {"message": "Registro exitoso. Revisá tu email para verificar la cuenta."}

@router.get("/verify/{token}")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.verification_token == token))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Token inválido")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="La cuenta ya fue verificada")
    if user.verification_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="El token expiró. Solicitá uno nuevo.")

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    await db.commit()

    return {"message": "¡Cuenta verificada! Ya podés iniciar sesión."}

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    error_msg = "Credenciales inválidas"

    if not user:
        raise HTTPException(status_code=401, detail=error_msg)

    if user.locked_until and user.locked_until > datetime.utcnow():
        if user.lockout_count >= LOCKOUT_PERMANENT:
            raise HTTPException(status_code=403, detail="Cuenta bloqueada por múltiples intentos fallidos. Debés recuperar tu contraseña por email para volver a acceder.")
        mins = int((user.locked_until - datetime.utcnow()).seconds / 60) + 1
        raise HTTPException(status_code=403, detail=f"Cuenta bloqueada temporalmente. Intentá en {mins} minutos")

    if not verify_password(data.password, user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= MAX_FAILED_ATTEMPTS:
            user.lockout_count += 1
            user.failed_logins = 0
            if user.lockout_count >= LOCKOUT_PERMANENT:
                user.locked_until = datetime.utcnow() + timedelta(days=3650)
                await db.commit()
                raise HTTPException(status_code=403, detail="Cuenta bloqueada por múltiples intentos fallidos. Debés recuperar tu contraseña por email para volver a acceder.")
            elif user.lockout_count == 2:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES_2)
                await db.commit()
                raise HTTPException(status_code=403, detail=f"Demasiados intentos fallidos. Cuenta bloqueada 60 minutos. Si no recordás tu contraseña, usá 'Recuperar acceso'.")
            else:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES_1)
        await db.commit()
        raise HTTPException(status_code=401, detail=error_msg)

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Cuenta no verificada. Revisá tu email.")

    user.failed_logins = 0
    user.locked_until = None
    await db.commit()

    token = create_token(user.id, user.email)
    return TokenResponse(access_token=token, user_name=user.name, user_email=user.email)

# --- Email de reset de contraseña ---
async def send_reset_email(email: str, name: str, token: str):
    reset_url = f"https://guiame.pro/reset.html?token={token}"
    html = f"""
    <div style="font-family:'DM Sans',Arial,sans-serif;background:#080b12;color:#f0f4ff;padding:40px;max-width:520px;margin:auto;border-radius:12px;">
      <div style="text-align:center;margin-bottom:24px;">
        <span style="font-family:Rajdhani,sans-serif;font-size:32px;">
          <span style="color:#f97316">Gu</span><span style="color:#60a5fa">IA</span><span style="color:#f97316">me</span>
        </span>
      </div>
      <h2 style="color:#f0f4ff;margin-bottom:8px;">Hola, {name} 👋</h2>
      <p style="color:#94a3c0;">Recibimos una solicitud para restablecer tu contraseña. Hacé clic en el botón para crear una nueva:</p>
      <div style="text-align:center;margin:32px 0;">
        <a href="{reset_url}" style="background:#f97316;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:16px;">
          Restablecer contraseña
        </a>
      </div>
      <p style="color:#94a3c0;font-size:13px;">Este link expira en 1 hora. Si no solicitaste este cambio, ignorá este mensaje.</p>
      <hr style="border-color:#1a2236;margin:24px 0;">
      <p style="color:#94a3c0;font-size:12px;text-align:center;">© 2026 GuIAme · Asistente Inteligente de Ciberseguridad</p>
    </div>
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": "GuIAme <noreply@guiame.pro>",
                "to": [email],
                "subject": "Restablecé tu contraseña de GuIAme",
                "html": html,
            },
        )

# --- Endpoints de recuperación ---
@router.post("/forgot-password", status_code=200)
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user and user.password_hash:
        token = secrets.token_hex(32)
        expires = datetime.utcnow() + timedelta(hours=1)
        user.reset_token = token
        user.reset_token_expires = expires
        await db.commit()
        await send_reset_email(user.email, user.name, token)
    return {"message": "Si el email existe en nuestro sistema, recibirás un link para restablecer tu contraseña."}

@router.post("/reset-password", status_code=200)
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    if len(data.new_password) < 12:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 12 caracteres")
    result = await db.execute(select(User).where(User.reset_token == data.token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Token inválido")
    if user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="El link expiró. Solicitá uno nuevo.")
    user.password_hash = hash_password(data.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.failed_logins = 0
    user.locked_until = None
    await db.commit()
    return {"message": "Contraseña restablecida correctamente. Ya podés iniciar sesión."}


# --- Reenvío de verificación ---
@router.post("/resend-verification", status_code=200)
async def resend_verification(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user and not user.is_verified:
        token = secrets.token_hex(32)
        expires = datetime.utcnow() + timedelta(hours=24)
        user.verification_token = token
        user.verification_token_expires = expires
        await db.commit()
        await send_verification_email(user.email, user.name, token)
    return {"message": "Si el email existe y la cuenta no está verificada, recibirás un nuevo link de verificación."}

# --- Google OAuth (id_token vía SDK nativo) ---
@router.post("/google", response_model=TokenResponse)
async def google_login(payload: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    credential = payload.credential

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": credential}
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Token de Google inválido")

    google_data = resp.json()

    if google_data.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Token no válido para esta aplicación")

    email = google_data.get("email")
    name = google_data.get("name", email.split("@")[0])

    if not email:
        raise HTTPException(status_code=400, detail="No se pudo obtener el email de Google")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            name=name,
            email=email,
            password_hash="",
            is_verified=True,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user.is_active:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")
    else:
        if not user.is_verified:
            user.is_verified = True
        user.failed_logins = 0
        user.locked_until = None
        await db.commit()

    token = create_token(user.id, user.email)
    return TokenResponse(access_token=token, user_name=user.name, user_email=user.email)


# --- Google OAuth (authorization code vía popup manual) ---
class GoogleCodeRequest:
    def __init__(self, code: str, redirect_uri: str):
        self.code = code
        self.redirect_uri = redirect_uri

from pydantic import BaseModel

class GoogleCodePayload(BaseModel):
    code: str
    redirect_uri: str

@router.post("/google-code", response_model=TokenResponse)
async def google_login_code(payload: GoogleCodePayload, db: AsyncSession = Depends(get_db)):
    # Canjear el authorization code por tokens de Google
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code":          payload.code,
                "client_id":     settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri":  payload.redirect_uri,
                "grant_type":    "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(status_code=401, detail="No se pudo canjear el código de Google")

    token_data = token_resp.json()
    id_token = token_data.get("id_token")

    if not id_token:
        raise HTTPException(status_code=401, detail="Google no devolvió id_token")

    # Verificar el id_token
    async with httpx.AsyncClient() as client:
        info_resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token}
        )

    if info_resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Token de Google inválido")

    google_data = info_resp.json()

    if google_data.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Token no válido para esta aplicación")

    email = google_data.get("email")
    name  = google_data.get("name", email.split("@")[0] if email else "Usuario")

    if not email:
        raise HTTPException(status_code=400, detail="No se pudo obtener el email de Google")

    # Buscar o crear usuario
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            name=name,
            email=email,
            password_hash="",
            is_verified=True,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user.is_active:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")
    else:
        if not user.is_verified:
            user.is_verified = True
        user.failed_logins = 0
        user.locked_until = None
        await db.commit()

    token = create_token(user.id, user.email)
    return TokenResponse(access_token=token, user_name=user.name, user_email=user.email)
