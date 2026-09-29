"""
Password reset flow: OTP generation, verification, and password update.
"""
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.password_reset_token import PasswordResetToken
from app.services.otp_service import create_otp, verify_otp
from app.services.sms_service import send_password_reset_otp_sms
from app.utils.security import hash_password
from app.utils.jwt import create_access_token
from fastapi import HTTPException, status
import secrets

RESET_TOKEN_EXPIRE_MINUTES = 15


async def request_password_reset(db: AsyncSession, mobile: str) -> str:
    """
    Request OTP for password reset.
    Verify phone number exists in database.
    Generate and send demo OTP.
    Return the generated OTP code.
    """
    result = await db.execute(select(User).where(User.mobile == mobile))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Phone number not registered. Please create an account."
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=400,
            detail="Account not verified. Please complete registration first."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is deactivated."
        )

    code = await create_otp(db, mobile, "PASSWORD_RESET")
    await send_password_reset_otp_sms(mobile, code)
    return code


async def verify_reset_otp_and_create_token(db: AsyncSession, mobile: str, otp_code: str) -> str:
    """
    Verify OTP for password reset.
    If valid, create and return a short-lived reset token.
    """
    await verify_otp(db, mobile, otp_code, "PASSWORD_RESET")

    reset_token = secrets.token_urlsafe(32)
    token_obj = PasswordResetToken(
        mobile=mobile,
        token=reset_token,
        expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
    )
    db.add(token_obj)
    await db.commit()

    return reset_token


async def reset_password(db: AsyncSession, reset_token: str, new_password: str) -> bool:
    """
    Verify reset token and update user password.
    Invalidate the token after use.
    """
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == reset_token)
    )
    token_obj = result.scalars().first()

    if not token_obj:
        raise HTTPException(
            status_code=400,
            detail="Invalid reset token. Please request a new password reset."
        )

    if token_obj.is_used:
        raise HTTPException(
            status_code=400,
            detail="Reset token has already been used. Please request a new password reset."
        )

    if datetime.utcnow() > token_obj.expires_at:
        token_obj.is_used = True
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="Reset token has expired. Please request a new password reset."
        )

    result = await db.execute(select(User).where(User.mobile == token_obj.mobile))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.password_hash = hash_password(new_password)
    token_obj.is_used = True
    await db.commit()

    return True
