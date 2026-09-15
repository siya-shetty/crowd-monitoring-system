from datetime import UTC, datetime, timedelta
from uuid import UUID
import jwt
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.user import User
password_hash = PasswordHash.recommended()
def hash_password(password: str) -> str: return password_hash.hash(password)
def verify_password(password: str, hashed_password: str) -> bool: return password_hash.verify(password, hashed_password)
def normalize_email(email: str) -> str: return email.strip().lower()
def get_user_by_email(database: Session, email: str) -> User | None: return database.scalar(select(User).where(User.email == normalize_email(email)))
def create_access_token(user_id: UUID) -> str:
    settings = get_settings(); expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires_at}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
def decode_access_token(token: str) -> UUID | None:
    settings = get_settings()
    try:
        subject = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]).get("sub")
        return UUID(subject) if subject else None
    except (jwt.InvalidTokenError, ValueError, TypeError): return None
