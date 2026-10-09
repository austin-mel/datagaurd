from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from src.schemas import CheckResponse, ErrorResponse, ProfileResponse, UploadResponse
from src.services.tabular import ParsedDataset, parse_dataset, validate_file_type
from src.services.profiling import profile_dataset
from src.services.validation import check_dataset
from src.services.catalog import Catalog
from src.settings import Settings

Sheet = Annotated[str | None, Form(description="Worksheet name; required for workbooks with multiple worksheets.")]
RuleSelection = Annotated[str | None, Form(description="Saved rule-set revision ID. Omit to use the default.")]
DataFile = Annotated[UploadFile, File(description="CSV, TSV, XLSX, or Parquet dataset.")]


def read_upload(file: UploadFile, settings: Settings, sheet_name: str | None = None) -> tuple[bytes, ParsedDataset]:
    validate_file_type(file.filename, file.content_type)
    content = file.file.read(settings.max_upload_bytes + 1)
    return content, parse_dataset(content, file.filename, settings, file.content_type, sheet_name)


def dataset_router(settings: Settings, catalog: Catalog) -> APIRouter:
    router = APIRouter(prefix="/datasets", tags=["Datasets"], responses={
        404: {"model": ErrorResponse, "description": "Rule set not found."},
        413: {"model": ErrorResponse, "description": "Dataset size limit exceeded."},
        415: {"model": ErrorResponse, "description": "Unsupported file type or encoding."},
        422: {"model": ErrorResponse, "description": "Invalid request or dataset structure."},
        503: {"model": ErrorResponse, "description": "Database or file storage unavailable."},
    })

    @router.post("/upload", response_model=UploadResponse, summary="Save and check a dataset",
                 description="Pins the selected rule revision, saves the original file, and checks the first version.")
    def upload(file: DataFile, rule_set_id: RuleSelection = None, sheet_name: Sheet = None) -> UploadResponse:
        content, parsed = read_upload(file, settings, sheet_name)
        return catalog.upload(content, parsed, rule_set_id=rule_set_id)

    @router.post("/profile", response_model=ProfileResponse, summary="Profile an uploaded dataset")
    def profile(file: DataFile, rule_set_id: RuleSelection = None, sheet_name: Sheet = None) -> ProfileResponse:
        rules = catalog.rule_set(rule_set_id).configuration
        _, dataset = read_upload(file, settings, sheet_name)
        return ProfileResponse(metadata=dataset.metadata, profile=profile_dataset(dataset, rules, settings.top_category_count))

    @router.post("/check", response_model=CheckResponse, summary="Check an uploaded dataset",
                 description="Stateless analysis. Completed checks return HTTP 200 even when validation fails.")
    def check(file: DataFile, rule_set_id: RuleSelection = None, sheet_name: Sheet = None) -> CheckResponse:
        rules = catalog.rule_set(rule_set_id).configuration
        return check_dataset(read_upload(file, settings, sheet_name)[1], rules, settings)

    return router
