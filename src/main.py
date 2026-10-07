from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.errors import InputError
from src.routes import dataset_router
from src.rules import load_rules
from src.schemas import ErrorDetail, ErrorResponse, HealthResponse
from src.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    application = FastAPI(
        title="DataGuard",
        version="0.1.0",
        description="Local CSV data-quality demo. Demo actor: local_operator.",
        openapi_tags=[{"name": "Health", "description": "Process health."},
                      {"name": "Datasets", "description": "Stateless CSV ingestion and analysis."}],
    )
    application.include_router(dataset_router(settings, load_rules(settings.rules_path)))

    @application.exception_handler(InputError)
    async def input_error_handler(request: Request, exc: InputError) -> JSONResponse:
        body = ErrorResponse(error=ErrorDetail(
            code=exc.code, message=exc.message, details=exc.details
        ))
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @application.exception_handler(RequestValidationError)
    async def request_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        body = ErrorResponse(error=ErrorDetail(
            code="invalid_request", message="The request does not match the endpoint schema.",
            details={"errors": [
                {"location": [str(part) for part in error["loc"]], "message": error["msg"]}
                for error in exc.errors()
            ]},
        ))
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @application.get("/health", tags=["Health"], response_model=HealthResponse,
                     summary="Check API health")
    def health() -> HealthResponse:
        return HealthResponse()

    return application


app = create_app()

