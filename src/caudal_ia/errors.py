import logging
from http import HTTPStatus
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from caudal_ia.request_validation import ContractValidationError
from caudal_ia.series_validation import InsufficientHistoryError, SeriesValidationError

VALIDATION_ERROR = "VALIDATION_ERROR"
UNAUTHORIZED = "UNAUTHORIZED"
PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
INVALID_SERIES = "INVALID_SERIES"
INTERNAL_ERROR = "INTERNAL_ERROR"
MODEL_NOT_READY = "MODEL_NOT_READY"

UNKNOWN_FIELD = "UNKNOWN_FIELD"
MISSING_FIELD = "MISSING_FIELD"
INVALID_FIELD = "INVALID_FIELD"
EXTRA_FORBIDDEN = "extra_forbidden"
MISSING = "missing"
FIRST_VALIDATION_ERROR_INDEX = 0
DEFAULT_VALIDATION_FIELD = "body"
RETRY_AFTER_SECONDS = "30"

VALIDATION_ERROR_MESSAGE = "La solicitud no cumple con el formato esperado."
PAYLOAD_TOO_LARGE_MESSAGE = "El tamaño del cuerpo supera el límite permitido."
INTERNAL_ERROR_MESSAGE = "Ocurrió un error interno al procesar la solicitud."


class ApiError(Exception):
    def __init__(
        self,
        status_code: int | HTTPStatus,
        code: str,
        message: str,
        details: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers
        super().__init__(message)


def build_error_body(
    code: str,
    message: str,
    details: dict[str, Any],
    request_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id or str(uuid4()),
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.status_code,
            content=build_error_body(error.code, error.message, error.details),
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        del request
        validation_error = error.errors()[FIRST_VALIDATION_ERROR_INDEX]
        location = validation_error.get("loc", ())
        field = str(location[-1]) if location else DEFAULT_VALIDATION_FIELD
        error_type = validation_error.get("type")
        reason = (
            UNKNOWN_FIELD
            if error_type == EXTRA_FORBIDDEN
            else MISSING_FIELD
            if error_type == MISSING
            else INVALID_FIELD
        )
        return JSONResponse(
            status_code=HTTPStatus.BAD_REQUEST,
            content=build_error_body(
                VALIDATION_ERROR,
                VALIDATION_ERROR_MESSAGE,
                {"field": field, "reason": reason},
            ),
        )

    @app.exception_handler(ContractValidationError)
    async def handle_contract_validation_error(
        request: Request, error: ContractValidationError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=HTTPStatus.BAD_REQUEST,
            content=build_error_body(
                VALIDATION_ERROR,
                str(error),
                {"field": error.field, "reason": error.reason},
            ),
        )

    @app.exception_handler(SeriesValidationError)
    async def handle_series_validation_error(
        request: Request, error: SeriesValidationError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=build_error_body(
                INVALID_SERIES,
                str(error),
                {"reason": error.reason, "index": error.index},
            ),
        )

    @app.exception_handler(InsufficientHistoryError)
    async def handle_insufficient_history_error(
        request: Request, error: InsufficientHistoryError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=build_error_body(
                INSUFFICIENT_HISTORY,
                str(error),
                {"received": error.received, "minimum": error.minimum},
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, error: Exception
    ) -> JSONResponse:
        del request
        logging.exception(
            "Unhandled exception while processing request", exc_info=error
        )
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=build_error_body(INTERNAL_ERROR, INTERNAL_ERROR_MESSAGE, {}),
        )
