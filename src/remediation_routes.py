from fastapi import APIRouter

from src.persistence_routes import Limit, Offset
from src.schemas import (
    ApprovalRequest, ErrorResponse, ExecutionResponse, Page, RecordChange, RejectionRequest,
    RemediationComparison, RemediationPreview, RemediationRequest, RemediationView,
)
from src.services.catalog import Catalog
from src.services.remediation import Remediations


def remediation_router(catalog: Catalog) -> APIRouter:
    service = Remediations(catalog)
    router = APIRouter(tags=["Corrections"], responses={
        404: {"model": ErrorResponse, "description": "Resource not found."},
        409: {"model": ErrorResponse, "description": "Invalid transition, missing preview, stale source or old-value mismatch."},
        413: {"model": ErrorResponse, "description": "The proposal or corrected file exceeds configured limits."},
        415: {"model": ErrorResponse, "description": "The stored source is not a supported CSV."},
        422: {"model": ErrorResponse, "description": "Invalid proposal, record selection or corrected CSV."},
        503: {"model": ErrorResponse, "description": "Storage, database or analysis unavailable; retrieve proposal status before retrying."},
    })

    @router.post("/remediations", response_model=RemediationView, status_code=201,
                 summary="Propose an exact replacement",
                 description="Copy source_version_id and content_sha256 from the latest version. Select one column and "
                 "explicit 1-based record numbers with their exact expected values. Proposals are immutable; changing "
                 "any input requires a new proposal, preview and approval.")
    def create(request: RemediationRequest) -> RemediationView:
        return service.create(request)

    @router.get("/datasets/{dataset_id}/remediations", response_model=Page[RemediationView],
                summary="List a dataset's correction proposals")
    def proposals(dataset_id: str, limit: Limit = 20, offset: Offset = 0) -> Page[RemediationView]:
        return service.list(dataset_id, limit, offset)

    @router.get("/remediations/{remediation_id}", response_model=RemediationView, summary="Get correction status and result IDs")
    def get(remediation_id: str) -> RemediationView:
        return service.get(remediation_id)

    @router.get("/remediations/{remediation_id}/records", response_model=Page[RecordChange],
                summary="Retrieve every selected record and replacement",
                description="Pages are ordered by record number. Old values are the verified source values recorded in the proposal.")
    def records(remediation_id: str, limit: Limit = 20, offset: Offset = 0) -> Page[RecordChange]:
        return service.records(remediation_id, limit, offset)

    @router.post("/remediations/{remediation_id}/preview", response_model=RemediationPreview,
                 summary="Preview the change without modifying CSV data",
                 description="Returns selected and changed counts, bounded samples, and an approval token. Use the records "
                 "endpoint to inspect the full selection. Generating another preview replaces the previous token.")
    def preview(remediation_id: str) -> RemediationPreview:
        return service.preview(remediation_id)

    @router.post("/remediations/{remediation_id}/approve", response_model=RemediationView,
                 summary="Approve the latest preview",
                 description="Submit preview_token from the latest preview. Approval records the current actor and time; "
                 "it does not execute the correction.")
    def approve(remediation_id: str, request: ApprovalRequest) -> RemediationView:
        return service.approve(remediation_id, request)

    @router.post("/remediations/{remediation_id}/reject", response_model=RemediationView,
                 summary="Reject a proposed correction with a reason")
    def reject(remediation_id: str, request: RejectionRequest) -> RemediationView:
        return service.reject(remediation_id, request)

    @router.post("/remediations/{remediation_id}/execute", response_model=ExecutionResponse,
                 summary="Create one corrected version and revalidate it",
                 description="Requires an approved proposal against the latest version. Rechecks its hash and old values. "
                 "Repeated execution returns the same version and check run, resuming an interrupted check if needed. "
                 "A failed check does not undo a committed correction. Retry a failed check through POST /versions/{version_id}/check.")
    def execute(remediation_id: str) -> ExecutionResponse:
        return service.execute(remediation_id)

    @router.get("/remediations/{remediation_id}/comparison", response_model=RemediationComparison,
                summary="Compare source and corrected results",
                description="Returns paginated cell changes and both versions' profiles, metrics and findings. The before run "
                "is fixed at execution; the after run is the latest check of the corrected version, including retries. "
                "Metric deltas are unavailable unless both runs completed under matching configurations. "
                "Read transition history through GET /datasets/{dataset_id}/audit.")
    def comparison(remediation_id: str, limit: Limit = 20, offset: Offset = 0) -> RemediationComparison:
        return service.compare(remediation_id, limit, offset)

    return router
