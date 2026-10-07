from typing import Annotated

from fastapi import APIRouter, File, Query, Response, UploadFile

from src.routes import read_upload
from src.schemas import (
    AffectedRecord, AuditView, DatasetView, ErrorResponse, Page, RunView,
    QualityMetrics, ReviewRequest, ReviewView, StoredFinding, UploadResponse, VersionView,
)
from src.services.catalog import Catalog

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def persistence_router(catalog: Catalog) -> APIRouter:
    router = APIRouter(tags=["History"], responses={
        404: {"model": ErrorResponse, "description": "Resource not found."},
        413: {"model": ErrorResponse, "description": "Upload limit exceeded."},
        415: {"model": ErrorResponse, "description": "Unsupported CSV file or encoding."},
        422: {"model": ErrorResponse, "description": "Invalid request or CSV."},
        503: {"model": ErrorResponse, "description": "Storage or database unavailable."},
    })

    @router.get("/datasets", response_model=Page[DatasetView], summary="List saved datasets")
    def datasets(limit: Limit = 20, offset: Offset = 0) -> Page[DatasetView]:
        return catalog.datasets(limit, offset)

    @router.get("/datasets/{dataset_id}", response_model=DatasetView, summary="Get a saved dataset")
    def dataset(dataset_id: str) -> DatasetView:
        return catalog.dataset(dataset_id)

    @router.get("/datasets/{dataset_id}/versions", response_model=Page[VersionView], summary="List immutable versions")
    def versions(dataset_id: str, limit: Limit = 20, offset: Offset = 0) -> Page[VersionView]:
        return catalog.versions(dataset_id, limit, offset)

    @router.post("/datasets/{dataset_id}/versions", response_model=UploadResponse,
                 summary="Upload another version", description="Example: upload the clean fixture after the dirty fixture. "
                 "The new version links to the latest committed version; both original files remain unchanged.")
    def upload_version(dataset_id: str, file: Annotated[UploadFile, File(description="A UTF-8 CSV file.")]) -> UploadResponse:
        content, parsed = read_upload(file, catalog.settings)
        return catalog.upload(content, parsed, dataset_id)

    @router.get("/versions/{version_id}", response_model=VersionView, summary="Get version metadata")
    def version(version_id: str) -> VersionView:
        return catalog.version(version_id)

    @router.get("/versions/{version_id}/file", response_class=Response, summary="Download the unchanged source CSV",
                responses={200: {"content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}}}})
    def source_file(version_id: str) -> Response:
        content, file_id = catalog.version_content(version_id)
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{file_id}"'})

    @router.post("/versions/{version_id}/check", response_model=RunView, summary="Check or recheck a saved version",
                 description="Creates a new run using current rules and settings. Failed runs remain in history; "
                 "retrying never reuploads or edits the version. Inspect processing_status separately from validation_status.")
    def check(version_id: str) -> RunView:
        return catalog.check(version_id)

    @router.get("/versions/{version_id}/check-runs", response_model=Page[RunView], summary="List check attempts")
    def runs(version_id: str, limit: Limit = 20, offset: Offset = 0) -> Page[RunView]:
        return catalog.runs(version_id, limit, offset)

    @router.get("/check-runs/{run_id}", response_model=RunView, summary="Get a saved check result")
    def run(run_id: str) -> RunView:
        return catalog.run(run_id)

    @router.get("/check-runs/{run_id}/findings", response_model=Page[StoredFinding], summary="List findings with persistent IDs")
    def findings(run_id: str, limit: Limit = 20, offset: Offset = 0) -> Page[StoredFinding]:
        return catalog.findings(run_id, limit, offset)

    @router.get("/findings/{finding_id}", response_model=StoredFinding, summary="Get finding evidence")
    def finding(finding_id: str) -> StoredFinding:
        return catalog.finding(finding_id)

    @router.get("/findings/{finding_id}/records", response_model=Page[AffectedRecord], summary="Retrieve all affected records")
    def records(finding_id: str, limit: Limit = 20, offset: Offset = 0) -> Page[AffectedRecord]:
        return catalog.affected_records(finding_id, limit, offset)

    @router.get("/datasets/{dataset_id}/audit", response_model=Page[AuditView], summary="Read append-only audit history")
    def audit(dataset_id: str, limit: Limit = 20, offset: Offset = 0) -> Page[AuditView]:
        return catalog.audit_events(dataset_id, limit, offset)

    @router.get("/check-runs/{run_id}/metrics", response_model=QualityMetrics, summary="Get saved quality metrics")
    def metrics(run_id: str) -> QualityMetrics:
        return catalog.metrics(run_id)

    review_router = APIRouter(tags=["Review"], responses=router.responses)

    @review_router.post("/findings/{finding_id}/reviews", response_model=ReviewView, status_code=201,
                 summary="Append a human review decision",
                 description="Use needs_correction, accepted_as_is, or dismissed. Acceptance and dismissal require a reason. "
                 "Example: {\"decision\":\"accepted_as_is\",\"reason\":\"Verified against the fictional source record.\"}. "
                 "Reviews do not change findings, metrics or dataset files.")
    def add_review(finding_id: str, request: ReviewRequest) -> ReviewView:
        return catalog.add_review(finding_id, request)

    @review_router.get("/findings/{finding_id}/reviews", response_model=Page[ReviewView],
                summary="Read a finding's decision history")
    def reviews(finding_id: str, limit: Limit = 20, offset: Offset = 0) -> Page[ReviewView]:
        return catalog.reviews(finding_id, limit, offset)

    combined = APIRouter()
    combined.include_router(router)
    combined.include_router(review_router)
    return combined

