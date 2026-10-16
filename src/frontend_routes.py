"""Versioned REST adapter for the DataGuard web workspace."""
from fastapi import APIRouter, Response
from pydantic import Field, JsonValue

from src.routes import DataFile, Sheet
from src.schemas import ApiModel, CellReviewRequest, ErrorResponse, UploadPolicy
from src.services.catalog import Catalog
from src.services.frontend_repository import FrontendRepository
from src.services.frontend_rules import EditorRuleset


class ValidateRequest(ApiModel):
    version: str = Field(min_length=1)


def frontend_router(catalog: Catalog) -> APIRouter:
    repository = FrontendRepository(catalog)
    router = APIRouter(prefix="/api/v1", tags=["Workspace"], responses={
        404: {"model": ErrorResponse}, 409: {"model": ErrorResponse},
        422: {"model": ErrorResponse}, 503: {"model": ErrorResponse},
    })

    @router.get("/workspace", summary="Get all datasets and the rule editor catalog")
    def workspace() -> dict[str, JsonValue]:
        return repository.getWorkspace()

    @router.get("/upload-policy", response_model=UploadPolicy)
    def upload_policy() -> UploadPolicy:
        return catalog.upload_policy()

    @router.post("/datasets", status_code=201, summary="Upload, persist and validate a dataset")
    def upload(file: DataFile, sheet_name: Sheet = None) -> dict[str, JsonValue]:
        return repository.upload(file.file.read(catalog.settings.max_upload_bytes + 1), file.filename or "",
                                 sheetName=sheet_name, contentType=file.content_type)

    @router.get("/datasets/{dataset_id}")
    def dataset(dataset_id: str) -> dict[str, JsonValue]:
        return repository.getDataset(dataset_id)

    @router.put("/datasets/{dataset_id}/ruleset")
    def ruleset(dataset_id: str, request: EditorRuleset) -> dict[str, JsonValue]:
        return repository.updateRuleset(dataset_id, request)

    @router.post("/datasets/{dataset_id}/validation")
    def validate(dataset_id: str, request: ValidateRequest) -> dict[str, JsonValue]:
        return repository.revalidate(dataset_id, request.version)

    @router.post("/datasets/{dataset_id}/cell-reviews")
    def review(dataset_id: str, request: CellReviewRequest) -> dict[str, JsonValue]:
        return repository.applyCellReview(dataset_id, request)

    @router.get("/datasets/{dataset_id}/file", response_class=Response)
    def download(dataset_id: str, version: str) -> Response:
        result = repository.download(dataset_id, version)
        return Response(result.content, media_type=result.media_type,
                        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'})

    return router
