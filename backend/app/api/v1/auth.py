from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from app.api.v1.dependencies import DatabaseSession, get_current_active_user
from app.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth import create_access_token, get_user_by_email, hash_password, normalize_email, verify_password
router = APIRouter(prefix="/auth", tags=["authentication"])
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, database: DatabaseSession) -> User:
    if get_user_by_email(database, str(payload.email)): raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    user = User(email=normalize_email(str(payload.email)), full_name=payload.full_name, hashed_password=hash_password(payload.password)); database.add(user)
    try: database.commit()
    except IntegrityError:
        database.rollback(); raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists") from None
    database.refresh(user); return user
@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, database: DatabaseSession) -> TokenResponse:
    user = get_user_by_email(database, str(payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password) or not user.is_active: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password", headers={"WWW-Authenticate":"Bearer"})
    return TokenResponse(access_token=create_access_token(user.id))
@router.get("/me", response_model=UserResponse)
def current_user(user: Annotated[User, Depends(get_current_active_user)]) -> User: return user
