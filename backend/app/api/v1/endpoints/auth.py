from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse, DemoLoginResponse, UserResponse

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Demo user
DEMO_USER = {
    "id": "1",
    "email": "admin@smartplan.ai",
    "name": "Admin User",
    "role": "admin",
    "password_hash": pwd_context.hash("admin123")
}


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


from datetime import datetime


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password"""
    if credentials.email != DEMO_USER["email"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if not pwd_context.verify(credentials.password, DEMO_USER["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    access_token = create_access_token(data={"sub": DEMO_USER["email"], "user_id": DEMO_USER["id"]})
    
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(**DEMO_USER)
    )


@router.post("/demo-login", response_model=DemoLoginResponse)
async def demo_login():
    """Demo login with predefined credentials"""
    access_token = create_access_token(data={"sub": DEMO_USER["email"], "user_id": DEMO_USER["id"]})
    
    return DemoLoginResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(**DEMO_USER)
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user():
    """Get current user info (mock)"""
    return UserResponse(**DEMO_USER)