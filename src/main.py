from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from src.errors import InputError
from src.routes import dataset_router
from src.persistence_routes import persistence_router
from src.remediation_routes import remediation_router
from src.rules import load_rules
from src.schemas import ErrorDetail, ErrorResponse, HealthResponse
from src.settings import Settings
from src.services.catalog import Catalog


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    rules = load_rules(settings.rules_path)
    catalog = Catalog(settings, rules)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            catalog.initialize()
            yield
        finally:
            catalog.database.close()

    application = FastAPI(
        title="DataGuard",
        version="0.3.0",
        lifespan=lifespan,
        description="Local CSV data-quality demo. Demo actor: local_operator.",
        openapi_tags=[{"name": "Health", "description": "Process health."},
                      {"name": "Datasets", "description": "CSV upload and analysis."},
                      {"name": "History", "description": "Saved versions, findings and audit history."},
                      {"name": "Review", "description": "Append-only human decisions; evidence and metrics stay unchanged."},
                      {"name": "Corrections", "description": "Preview, approve, execute and compare exact replacements."}],
    )
    application.state.catalog = catalog
    application.include_router(dataset_router(settings, rules, catalog))
    application.include_router(persistence_router(catalog))
    application.include_router(remediation_router(catalog))

    @application.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(status_code=503, content=ErrorResponse(error=ErrorDetail(
            code="database_unavailable", message="The metadata database is unavailable; retry later."
        )).model_dump(mode="json"))

    @application.exception_handler(OSError)
    async def storage_error_handler(request: Request, exc: OSError) -> JSONResponse:
        return JSONResponse(status_code=503, content=ErrorResponse(error=ErrorDetail(
            code="storage_unavailable", message="File storage is unavailable; retry later."
        )).model_dump(mode="json"))

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

