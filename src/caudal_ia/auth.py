import hmac
from http import HTTPStatus
from typing import Annotated

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from caudal_ia.config import TOKEN_ENCODING, get_settings
from caudal_ia.errors import UNAUTHORIZED, ApiError

UNAUTHORIZED_MESSAGE = "La solicitud no está autorizada."
BEARER_SCHEME = "bearer"
WWW_AUTHENTICATE_HEADERS = {"WWW-Authenticate": "Bearer"}

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Token de servicio que comparte el backend con el servicio IA.",
)


def require_service_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_scheme)
    ],
) -> None:
    """Allow the request only when it carries the configured service token."""
    if credentials is None or credentials.scheme.lower() != BEARER_SCHEME:
        raise _unauthorized()

    expected = get_settings().ia_service_token.get_secret_value()
    if not hmac.compare_digest(
        credentials.credentials.encode(TOKEN_ENCODING),
        expected.encode(TOKEN_ENCODING),
    ):
        raise _unauthorized()


def _unauthorized() -> ApiError:
    return ApiError(
        HTTPStatus.UNAUTHORIZED,
        UNAUTHORIZED,
        UNAUTHORIZED_MESSAGE,
        {},
        headers=WWW_AUTHENTICATE_HEADERS,
    )
