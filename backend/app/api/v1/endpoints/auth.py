from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr, field_validator
import re

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, generate_verification_code, generate_reset_token
)
from app.core.config import settings
from app.models.user import User, UserLanguage, UserCountry
from app.services.email_service import EmailService
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ─── Schemas ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email:        EmailStr
    password:     str
    name:         str
    phone:        str | None = None
    company_name: str | None = None
    country:      UserCountry = UserCountry.EG
    language:     UserLanguage = UserLanguage.AR

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("كلمة المرور يجب أن تكون 8 أحرف على الأقل")
        if not re.search(r"[A-Z]", v):
            raise ValueError("يجب أن تحتوي على حرف كبير")
        if not re.search(r"[0-9]", v):
            raise ValueError("يجب أن تحتوي على رقم")
        return v


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code:  str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token:    str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    user: dict


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # التحقق من عدم تكرار الإيميل
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ar": "البريد الإلكتروني مسجل مسبقاً", "en": "Email already registered"}
        )

    code = generate_verification_code()

    user = User(
        email             = body.email,
        password_hash     = hash_password(body.password),
        name              = body.name,
        phone             = body.phone,
        company_name      = body.company_name,
        country           = body.country,
        language          = body.language,
        verification_code = code,
        is_verified       = False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # إرسال كود التحقق
    background_tasks.add_task(
        EmailService.send_verification,
        email=body.email,
        name=body.name,
        code=code,
        language=body.language
    )

    return {
        "message": {
            "ar": "تم التسجيل! تحقق من بريدك الإلكتروني",
            "en": "Registered! Check your email"
        },
        "user_id": str(user.id)
    }


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or user.verification_code != body.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ar": "الكود غير صحيح", "en": "Invalid code"}
        )

    user.is_verified = True
    user.verification_code = None
    await db.commit()

    return {"message": {"ar": "تم تأكيد البريد الإلكتروني", "en": "Email verified"}}


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ar": "بيانات الدخول غير صحيحة", "en": "Invalid credentials"}
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ar": "يرجى تأكيد بريدك الإلكتروني أولاً", "en": "Please verify your email first"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ar": "الحساب موقوف", "en": "Account suspended"}
        )

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    token_data = {"sub": str(user.id), "email": user.email}

    return TokenResponse(
        access_token  = create_access_token(token_data),
        refresh_token = create_refresh_token(token_data),
        user = {
            "id":       str(user.id),
            "email":    user.email,
            "name":     user.name,
            "language": user.language,
            "country":  user.country,
        }
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ar": "Token غير صالح", "en": "Invalid token"}
        )

    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    token_data = {"sub": str(user.id), "email": user.email}
    return TokenResponse(
        access_token  = create_access_token(token_data),
        refresh_token = create_refresh_token(token_data),
        user = {"id": str(user.id), "email": user.email, "name": user.name}
    )


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # لا نفصح إذا الإيميل موجود أو لا (أمان)
    if user and user.is_verified:
        token = generate_reset_token()
        user.reset_token = token
        user.reset_token_exp = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.commit()

        background_tasks.add_task(
            EmailService.send_password_reset,
            email=user.email,
            name=user.name,
            token=token,
            language=user.language
        )

    return {"message": {"ar": "إذا البريد مسجل ستصله رسالة", "en": "If email exists, a reset link was sent"}}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.reset_token == body.token))
    user = result.scalar_one_or_none()

    if not user or not user.reset_token_exp:
        raise HTTPException(status_code=400, detail={"ar": "الرابط غير صالح", "en": "Invalid reset link"})

    if datetime.now(timezone.utc) > user.reset_token_exp:
        raise HTTPException(status_code=400, detail={"ar": "انتهت صلاحية الرابط", "en": "Link expired"})

    user.password_hash = hash_password(body.password)
    user.reset_token   = None
    user.reset_token_exp = None
    await db.commit()

    return {"message": {"ar": "تم تغيير كلمة المرور", "en": "Password updated"}}


# ─── Dependency: Current User ─────────────────────────────────────────────────
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
