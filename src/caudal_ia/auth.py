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
    """Allow the request only when it carries a current or previous token."""
    if credentials is None or credentials.scheme.lower() != BEARER_SCHEME:
        raise _unauthorized()

    provided = credentials.credentials.encode(TOKEN_ENCODING)
    # Compare against every accepted token before deciding, so the response time
    # does not reveal which token matched.
    matches = [
        hmac.compare_digest(provided, token.get_secret_value().encode(TOKEN_ENCODING))
        for token in get_settings().accepted_service_tokens()
    ]
    if not any(matches):
        raise _unauthorized()


def _unauthorized() -> ApiError:
    return ApiError(
        HTTPStatus.UNAUTHORIZED,
        UNAUTHORIZED,
        UNAUTHORIZED_MESSAGE,
        {},
        headers=WWW_AUTHENTICATE_HEADERS,
    )
