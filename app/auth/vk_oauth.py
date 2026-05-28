import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import settings

# State живёт 10 минут — нормальная верхняя граница для OAuth-redirect через VK.
VK_OAUTH_STATE_TTL_SECONDS = 600


class VKOAuthStateError(ValueError):
    """state в callback от VK невалиден: подпись не сошлась, истёк, или подмена."""


@dataclass(frozen=True, slots=True)
class VKUserInfo:
    vk_user_id: str
    full_name: str


def _hmac_sign(message: bytes) -> bytes:
    return hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        message,
        hashlib.sha256,
    ).digest()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def build_vk_oauth_state(now: float | None = None) -> str:
    """Подписанный HMAC state: `<nonce>.<ts>.<sig>`.

    Подпись на jwt_secret_key → отдельного хранилища (Redis/cookie) не нужно,
    но без знания секрета атакующий не сможет подделать state.
    """
    nonce = secrets.token_urlsafe(16)
    ts = str(int(now if now is not None else time.time()))
    payload = f"{nonce}.{ts}".encode()
    sig = _b64url_encode(_hmac_sign(payload))
    return f"{nonce}.{ts}.{sig}"


def verify_vk_oauth_state(state: str, *, now: float | None = None) -> None:
    """Бросает VKOAuthStateError если state невалиден или просрочен."""
    if not state:
        raise VKOAuthStateError("state missing")
    parts = state.split(".")
    if len(parts) != 3:
        raise VKOAuthStateError("state malformed")
    nonce, ts_str, sig = parts
    try:
        ts = int(ts_str)
    except ValueError as exc:
        raise VKOAuthStateError("state malformed") from exc

    expected_sig = _b64url_encode(_hmac_sign(f"{nonce}.{ts_str}".encode()))
    if not hmac.compare_digest(sig, expected_sig):
        raise VKOAuthStateError("state signature mismatch")

    current = now if now is not None else time.time()
    if current - ts > VK_OAUTH_STATE_TTL_SECONDS:
        raise VKOAuthStateError("state expired")
    if ts - current > VK_OAUTH_STATE_TTL_SECONDS:
        # Сильный clock skew или подделанный future-timestamp — отказ.
        raise VKOAuthStateError("state from the future")


class VKOAuthClient:
    def authorization_url(self) -> tuple[str, str]:
        """Возвращает (url, state). state ⊆ url, фронту state нужен для информации."""
        state = build_vk_oauth_state()
        query = urlencode(
            {
                "client_id": settings.vk_client_id,
                "redirect_uri": settings.vk_redirect_uri,
                "response_type": "code",
                "scope": "email",
                "state": state,
                "v": settings.vk_api_version,
            }
        )
        return f"{settings.vk_authorize_url}?{query}", state

    async def exchange_code_for_access_token(
        self,
        code: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> str:
        close_client = http_client is None
        client = http_client or httpx.AsyncClient()
        try:
            response = await client.get(
                settings.vk_token_url,
                params={
                    "client_id": settings.vk_client_id,
                    "client_secret": settings.vk_client_secret,
                    "redirect_uri": settings.vk_redirect_uri,
                    "code": code,
                },
            )
            response.raise_for_status()
            payload = response.json()
            access_token = payload.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise ValueError("VK token response does not include access_token")
            return access_token
        finally:
            if close_client:
                await client.aclose()

    async def get_user_info(
        self,
        access_token: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> VKUserInfo:
        close_client = http_client is None
        client = http_client or httpx.AsyncClient()
        try:
            response = await client.get(
                settings.vk_user_info_url,
                params={
                    "access_token": access_token,
                    "v": settings.vk_api_version,
                },
            )
            response.raise_for_status()
            payload = response.json()
            users = payload.get("response")
            if not isinstance(users, list) or not users:
                raise ValueError("VK user info response does not include user data")
            user = users[0]
            user_id = user.get("id")
            if user_id is None:
                raise ValueError("VK user info response does not include id")
            first_name = str(user.get("first_name") or "").strip()
            last_name = str(user.get("last_name") or "").strip()
            full_name = " ".join(part for part in (first_name, last_name) if part) or "VK User"
            return VKUserInfo(vk_user_id=str(user_id), full_name=full_name)
        finally:
            if close_client:
                await client.aclose()
