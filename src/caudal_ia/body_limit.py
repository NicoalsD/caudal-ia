from http import HTTPStatus

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from caudal_ia.config import get_settings
from caudal_ia.errors import (
    PAYLOAD_TOO_LARGE,
    PAYLOAD_TOO_LARGE_MESSAGE,
    build_error_body,
)

CONTENT_LENGTH_HEADER = b"content-length"
HTTP_REQUEST_MESSAGE = "http.request"
HTTP_RESPONSE_START_MESSAGE = "http.response.start"
NO_BODY = b""
INVALID_CONTENT_LENGTH_SIZE = 0


class BodyTooLargeError(Exception):
    """Raised inside the app when the bytes received so far exceed the limit."""


class BodyLimitMiddleware:
    """Reject request bodies larger than the configured limit.

    The declared Content-Length is checked first. The bytes actually received are
    counted too, so bodies sent without Content-Length (chunked) are limited as
    well. If the app has already started its response before the limit is hit,
    that response is left as it is.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit_bytes = get_settings().max_body_bytes
        if _declared_size_exceeds(scope, limit_bytes):
            await _send_payload_too_large(scope, receive, send, limit_bytes)
            return

        received_bytes = 0
        body_too_large = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received_bytes, body_too_large
            message = await receive()
            if message["type"] == HTTP_REQUEST_MESSAGE:
                received_bytes += len(message.get("body", NO_BODY))
                if received_bytes > limit_bytes:
                    body_too_large = True
                    raise BodyTooLargeError
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            # FastAPI turns a failed body read into its own 400 response. Once the
            # limit is hit, that response is dropped and replaced by the 413 below.
            if body_too_large and not response_started:
                return
            if message["type"] == HTTP_RESPONSE_START_MESSAGE:
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except BodyTooLargeError:
            pass
        if body_too_large and not response_started:
            await _send_payload_too_large(scope, receive, send, limit_bytes)


def _declared_size_exceeds(scope: Scope, limit_bytes: int) -> bool:
    content_length = next(
        (
            value
            for name, value in scope.get("headers", [])
            if name.lower() == CONTENT_LENGTH_HEADER
        ),
        None,
    )
    if content_length is None:
        return False
    try:
        body_size = int(content_length)
    except ValueError:
        body_size = INVALID_CONTENT_LENGTH_SIZE
    return body_size > limit_bytes


async def _send_payload_too_large(
    scope: Scope, receive: Receive, send: Send, limit_bytes: int
) -> None:
    response = JSONResponse(
        status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        content=build_error_body(
            PAYLOAD_TOO_LARGE,
            PAYLOAD_TOO_LARGE_MESSAGE,
            {"limit_bytes": limit_bytes},
        ),
    )
    await response(scope, receive, send)
