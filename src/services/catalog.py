import json
import logging
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import TypeVar
from uuid import uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from src.database import Database
from src.errors import InputError
from src.models import AuditEvent, Base, CheckRun, Dataset, DatasetVersion, FindingRecord, ReviewDecision
from src.rules import RuleSet
from src.schemas import (
    AffectedRecord, AuditView, CheckResponse, DatasetMetadata, DatasetView, Finding,
    Page, QualityMetrics, ReviewRequest, ReviewView, RunView, StoredFinding, UploadResponse, VersionView,
)
from src.services.tabular import ParsedDataset, parse_dataset
from src.services.storage import FileStorage
from src.services.validation import IMPLEMENTATION_VERSION, check_dataset
from src.settings import Settings

Model = TypeVar("Model", bound=Base)
View = TypeVar("View")
logger = logging.getLogger("dataguard")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require(session: Session, model: type[Model], identity: str) -> Model:
    value = session.get(model, identity)
    if value is None:
        raise InputError("not_found", "The requested resource does not exist.", 404)
    return value


def page_of(session: Session, query: Select[Model], convert: Callable[[Model], View],
            limit: int, offset: int) -> Page[View]:
    total = session.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = [convert(row) for row in session.scalars(query.limit(limit).offset(offset))]
    return Page(items=items, total=total, limit=limit, offset=offset)


def version_view(row: DatasetVersion) -> VersionView:
    return VersionView(
        id=row.id, dataset_id=row.dataset_id, number=row.number, parent_id=row.parent_id,
        file_id=row.file_id, metadata=DatasetMetadata.model_validate_json(row.metadata_json),
        created_at=datetime.fromisoformat(row.created_at),
    )


def finding_view(row: FindingRecord) -> StoredFinding:
    return StoredFinding(id=row.id, check_run_id=row.check_run_id,
                         **Finding.model_validate_json(row.payload_json).model_dump())


class Catalog:
    def __init__(self, settings: Settings, rules: RuleSet) -> None:
        self.settings = settings
        self.rules = rules
        self.database = Database(settings.storage_dir)
        self.files = FileStorage(settings.storage_dir)

    def initialize(self) -> None:
        self.database.initialize()
        self.reconcile()

    def reconcile(self) -> None:
        # Publication and reconciliation share SQLite's write lock, including across processes.
        with self.database.write() as session:
            self.files.reconcile(set(session.scalars(select(DatasetVersion.file_id))))

    def audit(self, session: Session, dataset_id: str, action: str, entity_id: str) -> None:
        session.add(AuditEvent(dataset_id=dataset_id, action=action, entity_id=entity_id,
                               actor=self.settings.actor, created_at=now()))

    def save_version(self, session: Session, dataset_id: str, content: bytes,
                     parsed: ParsedDataset, parent: DatasetVersion | None) -> DatasetVersion:
        version = DatasetVersion(
            id=str(uuid4()), dataset_id=dataset_id, number=parent.number + 1 if parent else 1,
            parent_id=parent.id if parent else None, file_id=f"{uuid4().hex}.csv",
            content_sha256=parsed.metadata.content_sha256, original_filename=parsed.metadata.original_filename,
            metadata_json=parsed.metadata.model_dump_json(), created_at=now(),
        )
        self.files.publish(version.file_id, content)
        session.add(version)
        session.flush()
        return version

    def upload(self, content: bytes, parsed: ParsedDataset, dataset_id: str | None = None) -> UploadResponse:
        try:
            with self.database.write() as session:
                if dataset_id is None:
                    dataset = Dataset(id=str(uuid4()), name=parsed.metadata.original_filename, created_at=now())
                    session.add(dataset)
                    session.flush()
                    self.audit(session, dataset.id, "dataset_created", dataset.id)
                else:
                    dataset = require(session, Dataset, dataset_id)
                previous = session.scalar(select(DatasetVersion).where(
                    DatasetVersion.dataset_id == dataset.id).order_by(DatasetVersion.number.desc()).limit(1))
                version = self.save_version(session, dataset.id, content, parsed, previous)
                self.audit(session, dataset.id, "version_uploaded", version.id)
            dataset_response = DatasetView.model_validate(dataset, from_attributes=True)
            version_response = version_view(version)
        except Exception:
            try:
                self.reconcile()
            except Exception:
                logger.warning("File reconciliation deferred until storage is available")
            raise
        try:
            run = self.check(version.id)
        except Exception as exc:
            raise InputError("analysis_unavailable", "The version was saved; retry its check when storage is available.",
                             503, {"dataset_id": dataset.id, "version_id": version.id}) from exc
        return UploadResponse(metadata=parsed.metadata, dataset=dataset_response, version=version_response, check_run=run)

    def parsed_version(self, version: DatasetVersion, settings: Settings | None = None) -> ParsedDataset:
        content = self.files.read(version.file_id, version.content_sha256)
        return parse_dataset(content, version.original_filename, settings or self.settings)

    def start_check(self, session: Session, version: DatasetVersion) -> CheckRun:
        reference_date = self.settings.reference_date or date.today()
        run_settings = self.settings.model_copy(update={"reference_date": reference_date})
        run = CheckRun(
            id=str(uuid4()), version_id=version.id, processing_status="running",
            configuration_json=self.rules.model_dump_json(), reference_date=reference_date.isoformat(),
            settings_json=run_settings.model_dump_json(exclude={"rules_path", "storage_dir", "reference_date", "actor"}),
            implementation_version=IMPLEMENTATION_VERSION, actor=self.settings.actor,
            created_at=now(), baseline_id=None,
        )
        session.add(run)
        session.flush()
        self.audit(session, version.dataset_id, "check_started", run.id)
        return run

    def check(self, version_id: str) -> RunView:
        with self.database.write() as session:
            version = require(session, DatasetVersion, version_id)
            run = self.start_check(session, version)
        return self.process_check(run.id)

    def process_check(self, run_id: str) -> RunView:
        with self.database.read() as session:
            run = require(session, CheckRun, run_id)
            if run.processing_status != "running":
                return self._run_view(session, run)
            version = require(session, DatasetVersion, run.version_id)
        try:
            if run.implementation_version != IMPLEMENTATION_VERSION:
                raise InputError("implementation_changed", "Create a new check using the current implementation.", 409)
            rules = RuleSet.model_validate_json(run.configuration_json)
            run_settings = self.settings.model_copy(update={
                **json.loads(run.settings_json), "reference_date": date.fromisoformat(run.reference_date), "actor": run.actor,
            })
            result = check_dataset(self.parsed_version(version, run_settings), rules, run_settings)
            with self.database.write() as session:
                stored = require(session, CheckRun, run.id)
                if stored.processing_status == "running":
                    stored.result_json = result.model_dump_json(exclude={"findings"})
                    stored.processing_status = "completed"
                    stored.completed_at = now()
                    for position, finding in enumerate(result.findings):
                        session.add(FindingRecord(id=str(uuid4()), check_run_id=run.id, position=position,
                                                  payload_json=finding.model_dump_json()))
                    self.audit(session, version.dataset_id, "check_completed", run.id)
        except Exception as exc:
            code = exc.code if isinstance(exc, InputError) else "processing_failed"
            logger.warning("Check processing failed (%s)", type(exc).__name__)
            with self.database.write() as session:
                stored = require(session, CheckRun, run.id)
                # A commit whose acknowledgement failed may already be durable.
                if stored.processing_status == "running":
                    stored.processing_status = "failed"
                    stored.error_code = code
                    stored.completed_at = now()
                    self.audit(session, version.dataset_id, "check_failed", run.id)
        return self.run(run.id)

    def _run_view(self, session: Session, row: CheckRun) -> RunView:
        result = None
        if row.result_json is not None and row.processing_status == "completed":
            document = json.loads(row.result_json)
            document["findings"] = [json.loads(finding.payload_json) for finding in session.scalars(
                select(FindingRecord).where(FindingRecord.check_run_id == row.id).order_by(FindingRecord.position))]
            result = CheckResponse.model_validate(document)
        return RunView(
            id=row.id, version_id=row.version_id, processing_status=row.processing_status,
            validation_status=result.validation_status if result else "not_available",
            configuration=RuleSet.model_validate_json(row.configuration_json),
            reference_date=date.fromisoformat(row.reference_date), implementation_version=row.implementation_version,
            settings_snapshot=json.loads(row.settings_json), baseline_id=row.baseline_id, actor=row.actor,
            created_at=datetime.fromisoformat(row.created_at),
            completed_at=datetime.fromisoformat(row.completed_at) if row.completed_at else None,
            error_code=row.error_code, result=result,
        )

    def datasets(self, limit: int, offset: int) -> Page[DatasetView]:
        with self.database.read() as session:
            return page_of(session, select(Dataset).order_by(Dataset.created_at, Dataset.id),
                           lambda row: DatasetView.model_validate(row, from_attributes=True), limit, offset)

    def dataset(self, dataset_id: str) -> DatasetView:
        with self.database.read() as session:
            return DatasetView.model_validate(require(session, Dataset, dataset_id), from_attributes=True)

    def versions(self, dataset_id: str, limit: int, offset: int) -> Page[VersionView]:
        with self.database.read() as session:
            require(session, Dataset, dataset_id)
            return page_of(session, select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id)
                           .order_by(DatasetVersion.number), version_view, limit, offset)

    def version(self, version_id: str) -> VersionView:
        with self.database.read() as session:
            return version_view(require(session, DatasetVersion, version_id))

    def version_content(self, version_id: str) -> tuple[bytes, str]:
        with self.database.read() as session:
            version = require(session, DatasetVersion, version_id)
            return self.files.read(version.file_id, version.content_sha256), version.file_id

    def runs(self, version_id: str, limit: int, offset: int) -> Page[RunView]:
        with self.database.read() as session:
            require(session, DatasetVersion, version_id)
            return page_of(session, select(CheckRun).where(CheckRun.version_id == version_id)
                           .order_by(CheckRun.created_at, CheckRun.id),
                           lambda row: self._run_view(session, row), limit, offset)

    def run(self, run_id: str) -> RunView:
        with self.database.read() as session:
            return self._run_view(session, require(session, CheckRun, run_id))

    def findings(self, run_id: str, limit: int, offset: int) -> Page[StoredFinding]:
        with self.database.read() as session:
            require(session, CheckRun, run_id)
            return page_of(session, select(FindingRecord).where(FindingRecord.check_run_id == run_id)
                           .order_by(FindingRecord.position), finding_view, limit, offset)

    def finding(self, finding_id: str) -> StoredFinding:
        with self.database.read() as session:
            return finding_view(require(session, FindingRecord, finding_id))

    def affected_records(self, finding_id: str, limit: int, offset: int) -> Page[AffectedRecord]:
        with self.database.read() as session:
            finding = require(session, FindingRecord, finding_id)
            run = require(session, CheckRun, finding.check_run_id)
            version = require(session, DatasetVersion, run.version_id)
            numbers = Finding.model_validate_json(finding.payload_json).affected_record_numbers
            parsed = self.parsed_version(version)
            items = [AffectedRecord(record_number=number,
                                    values=dict(zip(parsed.metadata.headers, parsed.records[number - 1], strict=True)))
                     for number in numbers[offset:offset + limit]]
            return Page(items=items, total=len(numbers), limit=limit, offset=offset)

    def audit_events(self, dataset_id: str, limit: int, offset: int) -> Page[AuditView]:
        with self.database.read() as session:
            require(session, Dataset, dataset_id)
            return page_of(session, select(AuditEvent).where(AuditEvent.dataset_id == dataset_id)
                           .order_by(AuditEvent.sequence),
                           lambda row: AuditView.model_validate(row, from_attributes=True), limit, offset)

    def metrics(self, run_id: str) -> QualityMetrics:
        run = self.run(run_id)
        return run.result.metrics if run.result else QualityMetrics()

    def add_review(self, finding_id: str, request: ReviewRequest) -> ReviewView:
        with self.database.write() as session:
            finding = require(session, FindingRecord, finding_id)
            run = require(session, CheckRun, finding.check_run_id)
            version = require(session, DatasetVersion, run.version_id)
            review = ReviewDecision(id=str(uuid4()), finding_id=finding_id, decision=request.decision,
                                    reason=request.reason, actor=self.settings.actor, created_at=now())
            session.add(review)
            self.audit(session, version.dataset_id, "review_added", review.id)
        return ReviewView.model_validate(review, from_attributes=True)

    def reviews(self, finding_id: str, limit: int, offset: int) -> Page[ReviewView]:
        with self.database.read() as session:
            require(session, FindingRecord, finding_id)
            return page_of(session, select(ReviewDecision).where(ReviewDecision.finding_id == finding_id)
                           .order_by(ReviewDecision.created_at, ReviewDecision.id),
                           lambda row: ReviewView.model_validate(row, from_attributes=True), limit, offset)

