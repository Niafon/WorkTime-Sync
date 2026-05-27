from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentEmployeeDep, get_db_session
from app.core.config import settings
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
    VKLoginResponse,
)
from app.schemas.common import ErrorResponse
from app.services.auth import AuthService, IssuedTokens, RefreshReuseDetectedError

router = APIRouter(prefix="/auth", tags=["auth"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
RefreshCookieDep = Annotated[str | None, Cookie(alias=settings.refresh_cookie_name)]

REFRESH_COOKIE_PATH = "/api/v1/auth"

error_responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
}


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        domain=settings.cookie_domain,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=REFRESH_COOKIE_PATH,
        domain=settings.cookie_domain,
    )


def _unauthorized_clearing_cookie(detail: str) -> JSONResponse:
    """401-ответ, явно очищающий refresh-cookie.

    Через raise HTTPException пробросить set-cookie нельзя — FastAPI делает
    новый Response для exception, теряя модификации injected response.
    """
    resp = JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": detail})
    _clear_refresh_cookie(resp)
    return resp


def _finalize(tokens: IssuedTokens, response: Response) -> AuthResponse:
    _set_refresh_cookie(response, tokens.refresh_token)
    return tokens.response


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses,
)
async def register(
    session: SessionDep,
    payload: RegisterRequest,
    response: Response,
) -> AuthResponse:
    try:
        tokens = await AuthService(session).register(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _finalize(tokens, response)


@router.post("/login", response_model=AuthResponse, responses=error_responses)
async def login(
    session: SessionDep,
    payload: LoginRequest,
    response: Response,
) -> AuthResponse:
    try:
        tokens = await AuthService(session).login(
            email=payload.email, password=payload.password
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return _finalize(tokens, response)


@router.get("/vk/login", response_model=VKLoginResponse)
async def vk_login(session: SessionDep) -> VKLoginResponse:
    return VKLoginResponse(authorization_url=AuthService(session).vk_authorization_url())


@router.get("/vk/callback", response_model=AuthResponse, responses=error_responses)
async def vk_callback(
    session: SessionDep,
    response: Response,
    code: str = Query(min_length=1),
) -> AuthResponse:
    try:
        tokens = await AuthService(session).authenticate_vk_code(code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _finalize(tokens, response)


@router.post("/refresh", response_model=AuthResponse, responses=error_responses)
async def refresh_token_endpoint(
    session: SessionDep,
    response: Response,
    refresh_cookie: RefreshCookieDep = None,
) -> AuthResponse | JSONResponse:
    if not refresh_cookie:
        return _unauthorized_clearing_cookie("refresh cookie missing")
    try:
        tokens = await AuthService(session).refresh(refresh_cookie)
    except RefreshReuseDetectedError:
        return _unauthorized_clearing_cookie(
            "session terminated: refresh token reuse detected"
        )
    except ValueError as exc:
        return _unauthorized_clearing_cookie(str(exc))
    return _finalize(tokens, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    session: SessionDep,
    refresh_cookie: RefreshCookieDep = None,
) -> Response:
    await AuthService(session).logout(refresh_cookie)
    # Создаём ответ с явно установленной delete-cookie (injected response при
    # status_code=204 теряет заголовки в некоторых вариантах ASGI).
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(resp)
    return resp


@router.get("/me", response_model=UserResponse, responses=error_responses)
async def get_current_employee_profile(
    current_employee: CurrentEmployeeDep,
) -> UserResponse:
    return UserResponse.from_employee(current_employee)
