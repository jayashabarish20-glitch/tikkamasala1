"""
OTP generation helper.
"""
import secrets
from app.config.settings import settings


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP. Uses fixed demo OTP (123456) in demo mode."""
    if settings.DEMO_MODE:
        return "123456"
    return "".join([str(secrets.randbelow(10)) for _ in range(length)])
