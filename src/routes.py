from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from src.rules import RuleSet
from src.schemas import CheckResponse, ErrorResponse, ProfileResponse, UploadResponse
from src.services.csv_parser import ParsedCsv, parse_csv, validate_file_type
from src.services.profiling import profile_dataset
from src.services.validation import check_dataset
from src.settings import Settings


def read_upload(file: UploadFile, settings: Settings) -> ParsedCsv:
    validate_file_type(file.filename, file.content_type)
    content = file.file.read(settings.max_upload_bytes + 1)
    return parse_csv(content, file.filename, settings, file.content_type)


def dataset_router(settings: Settings, rules: RuleSet) -> APIRouter:
    router = APIRouter(prefix="/datasets", tags=["Datasets"], responses={
        413: {"model": ErrorResponse, "description": "Upload byte or parsed-record limit exceeded."},
        415: {"model": ErrorResponse, "description": "Unsupported file type or encoding."},
        422: {"model": ErrorResponse, "description": "Missing upload or invalid CSV structure."},
    })

    @router.post("/upload", response_model=UploadResponse, summary="Inspect CSV upload metadata",
                 description="Upload facilities_clean.csv or facilities_dirty.csv. Both default fixtures have "
                             "150 records and seven columns. This endpoint is stateless; it does not store a file.")
    def upload(file: Annotated[UploadFile, File(description="A UTF-8 .csv file, optionally with a BOM.")]) -> UploadResponse:
        return UploadResponse(metadata=read_upload(file, settings).metadata)

    @router.post("/profile", response_model=ProfileResponse, summary="Profile an uploaded CSV",
                 description="Upload one CSV to inspect missing/distinct counts, observed types, finite numeric "
                             "ranges and top categories. Original strings are preserved.")
    def profile(file: Annotated[UploadFile, File(description="Example: facilities_clean.csv.")]) -> ProfileResponse:
        dataset = read_upload(file, settings)
        return ProfileResponse(metadata=dataset.metadata, profile=profile_dataset(dataset, rules, settings.top_category_count))

    @router.post("/check", response_model=CheckResponse, summary="Profile and validate an uploaded CSV",
                 description="Upload one CSV. A completed check returns HTTP 200 even when validation fails. "
                             "The clean fixture passes; the dirty fixture produces 21 rule/record pairs across 12 findings "
                             "with reference date 2026-10-07. Includes full affected membership and bounded samples.")
    def check(file: Annotated[UploadFile, File(description="Example: facilities_dirty.csv.")]) -> CheckResponse:
        return check_dataset(read_upload(file, settings), rules, settings)

    return router

