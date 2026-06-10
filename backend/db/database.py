from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector
from ..config import settings


engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(100), nullable=False)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role          = Column(String(20), default="user")  # user | admin
    is_active                  = Column(Boolean, default=True)
    is_verified                = Column(Boolean, default=False)
    verification_token         = Column(String(64), nullable=True)
    verification_token_expires = Column(DateTime, nullable=True)
    failed_logins  = Column(Integer, default=0)
    locked_until   = Column(DateTime, nullable=True)
    lockout_count  = Column(Integer, default=0)
    reset_token         = Column(String(64), nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    analyses = relationship("Analysis", back_populates="user")


class Analysis(Base):
    __tablename__ = "analyses"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    content_preview = Column(String(100), nullable=False)  # primeros 100 chars
    content_hash    = Column(String(64), nullable=False)    # sha256 del contenido
    channel         = Column(String(20), default="otro")
    input_type      = Column(String(10), default="msg")
    level           = Column(String(10), nullable=False)    # danger|warn|safe
    score           = Column(Integer, default=0)
    confidence      = Column(Integer, default=0)
    explanation     = Column(Text, nullable=True)
    signals         = Column(Text, nullable=True)           # JSON string
    recommendations = Column(Text, nullable=True)           # JSON string
    embedding       = Column(Vector(1536), nullable=True)   # OpenAI/Anthropic embedding
    created_at      = Column(DateTime, default=datetime.utcnow)

    user     = relationship("User", back_populates="analyses")
    feedback = relationship("Feedback", back_populates="analysis", uselist=False)


class Feedback(Base):
    __tablename__ = "feedback"

    id          = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_correct  = Column(Boolean, nullable=False)
    comment     = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    analysis = relationship("Analysis", back_populates="feedback")


class HeuristicPattern(Base):
    __tablename__ = "heuristic_patterns"

    id          = Column(Integer, primary_key=True, index=True)
    pattern     = Column(String(500), nullable=False)
    description = Column(String(200), nullable=False)
    severity    = Column(String(10), nullable=False)  # danger | warn
    points      = Column(Integer, nullable=False)
    is_active   = Column(Boolean, default=True)
    hit_count   = Column(Integer, default=0)          # veces que disparó
    created_at  = Column(DateTime, default=datetime.utcnow)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
