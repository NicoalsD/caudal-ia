from http import HTTPStatus

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from caudal_ia.config import get_settings
from caudal_ia.errors import (
    PAYLOAD_TOO_LARGE,
    PAYLOAD_TOO_LARGE_MESSAGE,
    build_error_body,
)

CONTENT_LENGTH_HEADER = b"content-length"


class BodyLimitMiddleware:
    """Reject requests whose Content-Length exceeds the configured limit.

    Requests without Content-Length are not measured by this middleware.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            content_length = next(
                (
                    value
                    for name, value in scope.get("headers", [])
                    if name.lower() == CONTENT_LENGTH_HEADER
                ),
                None,
            )
            if content_length is not None:
                try:
                    body_size = int(content_length)
                except ValueError:
                    body_size = 0
                limit_bytes = get_settings().max_body_bytes
                if body_size > limit_bytes:
                    response = JSONResponse(
                        status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        content=build_error_body(
                            PAYLOAD_TOO_LARGE,
                            PAYLOAD_TOO_LARGE_MESSAGE,
                            {"limit_bytes": limit_bytes},
                        ),
                    )
                    await response(scope, receive, send)
                    return

        await self.app(scope, receive, send)
