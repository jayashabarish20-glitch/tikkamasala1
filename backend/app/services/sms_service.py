"""
SMS provider abstraction with mock implementation for demo mode.
"""
import logging
from abc import ABC, abstractmethod
from app.config.settings import settings

logger = logging.getLogger(__name__)


class SMSProvider(ABC):
    @abstractmethod
    async def send_sms(self, mobile: str, message: str) -> bool:
        pass


class MockSMSProvider(SMSProvider):
    """Console-based mock for development/demo mode."""

    async def send_sms(self, mobile: str, message: str) -> bool:
        logger.info(f"\n{'='*50}")
        logger.info(f"MOCK SMS TO: {mobile}")
        logger.info(f"MESSAGE: {message}")
        logger.info(f"{'='*50}\n")
        print(f"\n{'='*50}")
        print(f"MOCK SMS TO: {mobile}")
        print(f"MESSAGE: {message}")
        print(f"{'='*50}\n")
        return True


class MSG91Provider(SMSProvider):
    """MSG91 SMS provider stub — wire up API key when ready."""

    async def send_sms(self, mobile: str, message: str) -> bool:
        import httpx
        url = "https://api.msg91.com/api/sendhttp.php"
        params = {
            "authkey": settings.SMS_API_KEY,
            "mobiles": mobile,
            "message": message,
            "sender": settings.SMS_SENDER_ID,
            "route": "4",
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=10)
                return resp.status_code == 200
        except Exception as e:
            logger.error("MSG91 SMS failed: %s", type(e).__name__)
            return False


class TwoFactorProvider(SMSProvider):
    """
    2Factor Manual OTP SMS provider.
    API: GET https://2factor.in/API/V1/{APIKEY}/SMS/{MOBILE}/{OTP}/{TEMPLATE}
    Official docs: /SMS/:phone_number/:otp_value/:otp_template_name
    TEMPLATE defaults to AUTOGEN (account default); override via SMS_OTP_TEMPLATE in .env.
    Response: {"Status": "Success", "Details": "<session-id>"}
           or {"Status": "Error",   "Details": "<reason>"}
    """

    _BASE_URL = "https://2factor.in/API/V1"

    @staticmethod
    def _normalize_mobile(mobile: str) -> str:
        """Return 10-digit Indian mobile number, stripping country code."""
        mobile = mobile.strip().replace(" ", "").replace("-", "")
        if mobile.startswith("+91"):
            mobile = mobile[3:]
        elif mobile.startswith("91") and len(mobile) == 12:
            mobile = mobile[2:]
        return mobile

    @staticmethod
    def _extract_otp(message: str) -> str:
        """
        Extract the numeric OTP from the backend-generated message text.
        Messages follow the pattern: '...OTP is 123456...'
        Returns the OTP string, or raises ValueError if not found.
        """
        import re
        match = re.search(r'\bOTP is (\d+)\b', message)
        if not match:
            raise ValueError("Could not extract OTP from message")
        return match.group(1)

    async def send_sms(self, mobile: str, message: str) -> bool:
        import httpx
        import json as _json

        try:
            otp = self._extract_otp(message)
        except ValueError:
            logger.error("2Factor SMS: OTP extraction failed from message")
            return False

        mobile_10 = self._normalize_mobile(mobile)
        # Correct parameter order per official docs: /SMS/{phone}/{otp_value}/{template}
        template = settings.SMS_OTP_TEMPLATE or "AUTOGEN"
        url = f"{self._BASE_URL}/{settings.SMS_API_KEY}/SMS/{mobile_10}/{otp}/{template}"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)

            content_type = resp.headers.get("content-type", "")
            status_code = resp.status_code
            body = resp.text

            logger.debug("2Factor response: HTTP %s | Content-Type: %s | Body: %s", status_code, content_type, body[:300])

            if "application/json" in content_type or body.lstrip().startswith("{"):
                try:
                    data = _json.loads(body)
                    if data.get("Status") == "Success":
                        return True
                    logger.error(
                        "2Factor SMS rejected: HTTP %s | Status=%s | Details=%s",
                        status_code, data.get("Status"), data.get("Details"),
                    )
                    return False
                except _json.JSONDecodeError:
                    logger.error("2Factor SMS: JSON parse failed | HTTP %s | Body: %s", status_code, body[:300])
                    return False

            logger.error("2Factor SMS non-JSON response: HTTP %s | Content-Type: %s | Body: %s", status_code, content_type, body[:300])
            return False

        except httpx.RequestError as e:
            logger.error("2Factor SMS network error: %s", type(e).__name__)
            return False
        except Exception as e:
            logger.error("2Factor SMS unexpected error: %s", type(e).__name__)
            return False


def get_sms_provider() -> SMSProvider:
    provider = settings.SMS_PROVIDER.lower()
    if provider == "2factor":
        return TwoFactorProvider()
    if provider == "msg91":
        return MSG91Provider()
    return MockSMSProvider()


async def send_otp_sms(mobile: str, otp: str) -> bool:
    provider = get_sms_provider()
    message = (
        f"Tikha Masala Chat Corner: Your verification OTP is {otp}. "
        f"Valid for 10 minutes. Do not share with anyone."
    )
    return await provider.send_sms(mobile, message)


async def send_delivery_otp_sms(mobile: str, otp: str) -> bool:
    provider = get_sms_provider()
    message = (
        f"Tikha Masala Chat Corner: Your delivery verification OTP is {otp}. "
        f"Share this OTP with the delivery person when receiving your order."
    )
    return await provider.send_sms(mobile, message)


async def send_password_reset_otp_sms(mobile: str, otp: str) -> bool:
    provider = get_sms_provider()
    message = (
        f"Tikha Masala Chat Corner: Your password reset OTP is {otp}. "
        f"Valid for 10 minutes. Do not share with anyone."
    )
    return await provider.send_sms(mobile, message)
