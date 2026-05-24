from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import settings


@dataclass(frozen=True, slots=True)
class VKUserInfo:
    vk_user_id: str
    full_name: str


class VKOAuthClient:
    def authorization_url(self) -> str:
        query = urlencode(
            {
                "client_id": settings.vk_client_id,
                "redirect_uri": settings.vk_redirect_uri,
                "response_type": "code",
                "scope": "email",
                "v": settings.vk_api_version,
            }
        )
        return f"{settings.vk_authorize_url}?{query}"

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
