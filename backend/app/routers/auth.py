"""Auth endpoints: register (with email verification), login, refresh,
forgot/reset password via emailed OTP."""
import logging
import random
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..config import settings
from ..database import get_db
from ..models import User
from ..schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
    UserOut,
    VerifyEmailRequest,
)
from ..services.email_service import send_email
from ..utils.timeutil import utcnow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_email_configured = bool(settings.smtp_host or settings.sendgrid_api_key)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    token = secrets.token_urlsafe(32)
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        company_name=payload.company_name,
        industry=payload.industry,
        state=payload.state,
        gstin=payload.gstin,
        verification_token=token,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    verify_url = f"{settings.frontend_origin}/verify-email?token={token}"
    send_email(
        user.email,
        "Verify your TenderRadar account",
        f"<p>Welcome to TenderRadar!</p><p><a href='{verify_url}'>Click here to "
        f"verify your email</a> and activate tender alerts.</p>",
    )

    body = {"user": UserOut.model_validate(user).model_dump(),
            "message": "Registered. Check your email to verify your account."}
    if not _email_configured:
        # Dev convenience: no mail provider configured, surface the token
        body["dev_verification_token"] = token
    return body


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.verification_token == payload.token))
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired verification token")
    user.is_verified = True
    user.verification_token = None
    db.commit()
    return {"message": "Email verified. You can now log in."}


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled — contact support")
    user.last_login_at = utcnow()
    db.commit()
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    data = decode_token(payload.refresh_token, "refresh")
    user = db.get(User, int(data["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or disabled")
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    generic = {"message": "If that email is registered, a reset OTP has been sent."}
    if not user:
        return generic  # don't leak account existence
    otp = f"{random.SystemRandom().randint(0, 999999):06d}"
    user.reset_otp = otp
    user.reset_otp_expires = utcnow() + timedelta(minutes=15)
    db.commit()
    send_email(
        user.email,
        "TenderRadar password reset OTP",
        f"<p>Your password reset OTP is <b style='font-size:20px'>{otp}</b>. "
        f"It expires in 15 minutes.</p>",
    )
    if not _email_configured:
        return {**generic, "dev_otp": otp}
    return generic


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if (not user or not user.reset_otp or user.reset_otp != payload.otp
            or not user.reset_otp_expires or user.reset_otp_expires < utcnow()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired OTP")
    user.password_hash = hash_password(payload.new_password)
    user.reset_otp = None
    user.reset_otp_expires = None
    db.commit()
    return {"message": "Password reset. You can now log in."}
