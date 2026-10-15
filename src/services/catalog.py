import csv
import hashlib
import io
import json
import logging
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import TypeVar
from uuid import uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import ScalarSelect

from src.database import Database
from src.errors import InputError
from src.models import AuditEvent, Base, CheckRun, Dataset, DatasetVersion, FindingRecord, ReviewDecision, RuleSetRecord
from src.rules import RuleSet, StatisticalSettings, UniqueRule
from src.schemas import (
    AffectedRecord, AuditView, CheckResponse, DatasetDetail, DatasetMetadata, DatasetView, Finding,
    Page, QualityMetrics, ReviewRequest, ReviewView, RuleSetView, RunView, StoredFinding, UploadResponse, UploadPolicy, VersionView,
    CellReviewRequest, CellReviewGroup, IgnoredCell, VersionReviewState, ReviewedCell,
)
from src.services.cell_review import cell_groups, cell_value, rule_signature
from src.services.identifiers import identifier_column, resolved_rules
from src.services.tabular import MEDIA_TYPES, ParsedDataset, parse_dataset
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


def run_order() -> ScalarSelect[int]:
    # Windows timestamps can tie. The audit sequence records actual insertion order.
    return select(AuditEvent.sequence).where(AuditEvent.entity_id == CheckRun.id,
                                             AuditEvent.action == "check_started").scalar_subquery()


class Catalog:
    def __init__(self, settings: Settings, rules: RuleSet) -> None:
        self.settings = settings
        self.rules = rules
        self.database = Database(settings.storage_dir)
        self.files = FileStorage(settings.storage_dir)
        self.default_rule_set_id = ""

    def initialize(self) -> None:
        self.database.initialize()
        with self.database.write() as session:
            self.default_rule_set_id = self._register_rules(session, self.rules, reuse=True).id
            for dataset in session.scalars(select(Dataset).where(Dataset.rule_set_id.is_(None))):
                previous = session.scalar(select(CheckRun).join(DatasetVersion, CheckRun.version_id == DatasetVersion.id).where(
                    DatasetVersion.dataset_id == dataset.id).order_by(CheckRun.created_at.desc(), CheckRun.id.desc()).limit(1))
                if previous:
                    rules = RuleSet.model_validate_json(previous.configuration_json)
                    settings = self.settings.model_copy(update=json.loads(previous.settings_json))
                    dataset.rule_set_id = self._register_rules(session, rules, reuse=True, settings=settings).id
                else:
                    dataset.rule_set_id = self.default_rule_set_id
                self.audit(session, dataset.id, "rule_set_assigned", dataset.rule_set_id)
        self.reconcile()

    def _register_rules(self, session: Session, rules: RuleSet, *, reuse: bool = False,
                        settings: Settings | None = None) -> RuleSetRecord:
        # Revalidate even model instances: model_copy/update can otherwise bypass schema validation.
        rules = RuleSet.model_validate(rules.model_dump())
        defaults = settings or self.settings
        statistics = rules.statistics or StatisticalSettings.model_validate(
            {name: getattr(defaults, name) for name in StatisticalSettings.model_fields})
        rules = rules.model_copy(update={"name": rules.name.strip(), "statistics": statistics}, deep=True)
        document = json.dumps(rules.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(document.encode()).hexdigest()
        if reuse:
            existing = session.scalar(select(RuleSetRecord).where(RuleSetRecord.configuration_sha256 == digest)
                                      .order_by(RuleSetRecord.revision).limit(1))
            if existing:
                return existing
        parent = session.scalar(select(RuleSetRecord).where(RuleSetRecord.name == rules.name)
                                .order_by(RuleSetRecord.revision.desc()).limit(1))
        row = RuleSetRecord(id=str(uuid4()), name=rules.name, revision=parent.revision + 1 if parent else 1,
                            parent_id=parent.id if parent else None, configuration_json=document,
                            configuration_sha256=digest, actor=self.settings.actor, created_at=now())
        session.add(row)
        session.flush()
        return row

    def _rule_view(self, row: RuleSetRecord) -> RuleSetView:
        return RuleSetView(id=row.id, name=row.name, revision=row.revision, parent_id=row.parent_id,
                           configuration=RuleSet.model_validate_json(row.configuration_json),
                           configuration_sha256=row.configuration_sha256, actor=row.actor,
                           created_at=datetime.fromisoformat(row.created_at), is_default=row.id == self.default_rule_set_id)

    def create_rule_set(self, rules: RuleSet) -> RuleSetView:
        with self.database.write() as session:
            row = self._register_rules(session, rules)
        return self._rule_view(row)

    def rule_sets(self, limit: int, offset: int) -> Page[RuleSetView]:
        with self.database.read() as session:
            return page_of(session, select(RuleSetRecord).order_by(RuleSetRecord.name, RuleSetRecord.revision),
                           self._rule_view, limit, offset)

    def rule_set(self, rule_set_id: str | None = None) -> RuleSetView:
        with self.database.read() as session:
            return self._rule_view(require(session, RuleSetRecord, rule_set_id or self.default_rule_set_id))

    def assign_rules(self, dataset_id: str, rule_set_id: str) -> DatasetView:
        with self.database.write() as session:
            dataset = require(session, Dataset, dataset_id)
            require(session, RuleSetRecord, rule_set_id)
            if dataset.rule_set_id != rule_set_id:
                dataset.rule_set_id = rule_set_id
                self.audit(session, dataset.id, "rule_set_assigned", rule_set_id)
        return DatasetView.model_validate(dataset, from_attributes=True)

    def reconcile(self) -> None:
        # Publication and reconciliation share SQLite's write lock, including across processes.
        with self.database.write() as session:
            self.files.reconcile(set(session.scalars(select(DatasetVersion.file_id))))

    def audit(self, session: Session, dataset_id: str, action: str, entity_id: str, description: str = "") -> None:
        session.add(AuditEvent(dataset_id=dataset_id, action=action, entity_id=entity_id,
                               actor=self.settings.actor, created_at=now(), description=description))

    def save_version(self, session: Session, dataset_id: str, content: bytes,
                     parsed: ParsedDataset, parent: DatasetVersion | None,
                     review_state: VersionReviewState | None = None) -> DatasetVersion:
        version = DatasetVersion(
            id=str(uuid4()), dataset_id=dataset_id, number=parent.number + 1 if parent else 1,
            parent_id=parent.id if parent else None, file_id=f"{uuid4().hex}.{parsed.metadata.format}",
            content_sha256=parsed.metadata.content_sha256, original_filename=parsed.metadata.original_filename,
            metadata_json=parsed.metadata.model_dump_json(), created_at=now(),
            review_state_json=(review_state or VersionReviewState()).model_dump_json(),
        )
        self.files.publish(version.file_id, content)
        session.add(version)
        session.flush()
        return version

    def upload(self, content: bytes, parsed: ParsedDataset, dataset_id: str | None = None,
               rule_set_id: str | None = None) -> UploadResponse:
        try:
            with self.database.write() as session:
                if dataset_id is None:
                    assignment = require(session, RuleSetRecord, rule_set_id or self.default_rule_set_id)
                    dataset = Dataset(id=str(uuid4()), name=parsed.metadata.original_filename, created_at=now(),
                                      rule_set_id=assignment.id)
                    session.add(dataset)
                    session.flush()
                    self.audit(session, dataset.id, "dataset_created", dataset.id)
                else:
                    dataset = require(session, Dataset, dataset_id)
                previous = session.scalar(select(DatasetVersion).where(
                    DatasetVersion.dataset_id == dataset.id).order_by(DatasetVersion.number.desc()).limit(1))
                version = self.save_version(session, dataset.id, content, parsed, previous)
                self.audit(session, dataset.id, "version_uploaded", version.id,
                           f"{self.settings.actor} · {parsed.metadata.original_filename} · v{version.number}")
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
        metadata = DatasetMetadata.model_validate_json(version.metadata_json)
        return parse_dataset(content, version.original_filename, settings or self.settings, sheet_name=metadata.sheet_name,
                             allow_empty=metadata.row_count == 0 and version.parent_id is not None, internal_snapshot=True)

    def start_check(self, session: Session, version: DatasetVersion) -> CheckRun:
        current = self._latest_run(session, version.id)
        if current and current.processing_status == "running":
            raise InputError("validation_running", "Wait for validation to finish before starting another run.", 409)
        dataset = require(session, Dataset, version.dataset_id)
        assignment = require(session, RuleSetRecord, dataset.rule_set_id or self.default_rule_set_id)
        rules = RuleSet.model_validate_json(assignment.configuration_json)
        reference_date = self.settings.reference_date or date.today()
        run_settings = self.settings.model_copy(update={"reference_date": reference_date,
                                                        **(rules.statistics.model_dump() if rules.statistics else {})})
        run = CheckRun(
            id=str(uuid4()), version_id=version.id, processing_status="running",
            configuration_json=assignment.configuration_json, rule_set_id=assignment.id, reference_date=reference_date.isoformat(),
            settings_json=run_settings.model_dump_json(exclude={"rules_path", "storage_dir", "reference_date", "actor"}),
            implementation_version=IMPLEMENTATION_VERSION, actor=self.settings.actor,
            created_at=now(), baseline_id=version.parent_id,
            review_state_json=version.review_state_json,
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
            baseline = require(session, DatasetVersion, run.baseline_id) if run.baseline_id else None
        try:
            if run.implementation_version != IMPLEMENTATION_VERSION:
                raise InputError("implementation_changed", "Create a new check using the current implementation.", 409)
            rules = RuleSet.model_validate_json(run.configuration_json)
            run_settings = self.settings.model_copy(update={
                **json.loads(run.settings_json), "reference_date": date.fromisoformat(run.reference_date), "actor": run.actor,
            })
            result = check_dataset(self.parsed_version(version, run_settings), rules, run_settings,
                                   self.parsed_version(baseline, run_settings) if baseline else None, run.baseline_id,
                                   VersionReviewState.model_validate_json(run.review_state_json))
            with self.database.write() as session:
                stored = require(session, CheckRun, run.id)
                if stored.processing_status == "running":
                    stored.result_json = result.model_dump_json(exclude={"findings"})
                    stored.processing_status = "completed"
                    stored.completed_at = now()
                    saved_version = require(session, DatasetVersion, stored.version_id)
                    state = VersionReviewState.model_validate_json(saved_version.review_state_json)
                    state.review_changed = False
                    state.data_changed = False
                    state.pending_groups = None
                    saved_version.review_state_json = state.model_dump_json()
                    for position, finding in enumerate(result.findings):
                        session.add(FindingRecord(id=str(uuid4()), check_run_id=run.id, position=position,
                                                  payload_json=finding.model_dump_json()))
                    self.audit(session, version.dataset_id, "check_completed", run.id,
                               f"v{version.number} · Validation results saved.")
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
            error_code=row.error_code, result=result, rule_set_id=row.rule_set_id,
        )

    def datasets(self, limit: int, offset: int) -> Page[DatasetView]:
        with self.database.read() as session:
            return page_of(session, select(Dataset).order_by(Dataset.created_at, Dataset.id),
                           lambda row: DatasetView.model_validate(row, from_attributes=True), limit, offset)

    def dataset(self, dataset_id: str) -> DatasetView:
        with self.database.read() as session:
            return DatasetView.model_validate(require(session, Dataset, dataset_id), from_attributes=True)

    def _latest_run(self, session: Session, version_id: str) -> CheckRun | None:
        return session.scalar(select(CheckRun).where(CheckRun.version_id == version_id)
                              .order_by(CheckRun.created_at.desc(), run_order().desc(), CheckRun.id.desc()).limit(1))

    def _selected_version(self, session: Session, dataset_id: str, version: str | None) -> DatasetVersion | None:
        query = select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id)
        if version is None:
            return session.scalar(query.order_by(DatasetVersion.number.desc()).limit(1))
        if version.startswith("v") and version[1:].isdigit():
            selected = session.scalar(query.where(DatasetVersion.number == int(version[1:])))
        else:
            selected = session.scalar(query.where(DatasetVersion.id == version))
        if selected is None:
            raise InputError("not_found", "The selected version does not belong to this dataset.", 404)
        return selected

    def _cell_groups(self, version: DatasetVersion, run: RunView | None, state: VersionReviewState) -> list[CellReviewGroup] | None:
        if run and run.processing_status in {"running", "failed"}:
            return None
        if state.pending_groups is not None:
            return state.pending_groups
        if not run or not run.result:
            return None
        return cell_groups(self.parsed_version(version), run.result)

    def _detail(self, session: Session, dataset: Dataset, version_id: str | None = None) -> DatasetDetail:
        latest = session.scalar(select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)
                                .order_by(DatasetVersion.number.desc()).limit(1))
        selected = self._selected_version(session, dataset.id, version_id) if version_id else latest
        if selected and selected.dataset_id != dataset.id:
            raise InputError("not_found", "The selected version does not belong to this dataset.", 404)
        run = self._latest_run(session, selected.id) if selected else None
        assignment = require(session, RuleSetRecord, dataset.rule_set_id or self.default_rule_set_id)
        upload = session.scalar(select(AuditEvent).join(DatasetVersion, AuditEvent.entity_id == DatasetVersion.id)
                                .where(AuditEvent.dataset_id == dataset.id, AuditEvent.action == "version_uploaded",
                                       DatasetVersion.number <= selected.number)
                                .order_by(DatasetVersion.number.desc()).limit(1)) if selected else None
        # Filter before selecting history; internal proposal/run-start events must not crowd it out.
        events = session.scalars(select(AuditEvent).where(AuditEvent.dataset_id == dataset.id,
            AuditEvent.action.in_(["version_uploaded", "check_completed", "rule_set_assigned", "version_corrected", "findings_ignored"]))
            .order_by(AuditEvent.sequence)).all()
        state = VersionReviewState.model_validate_json(selected.review_state_json) if selected else VersionReviewState()
        run_view = self._run_view(session, run) if run else None
        rules = RuleSet.model_validate_json(assignment.configuration_json)
        headers = DatasetMetadata.model_validate_json(selected.metadata_json).headers if selected else []
        identifier, identifier_reason = identifier_column(rules, headers)
        changed = run is None or json.loads(run.configuration_json) != json.loads(assignment.configuration_json)
        old_scores = bool(run_view and run_view.result and not run_view.result.metric_semantics
                          and run_view.result.implementation_version not in {"tabular-validation/2.0.0", "tabular-validation/2.1.0"})
        uploaded_version = require(session, DatasetVersion, upload.entity_id) if upload else None
        uploaded_metadata = DatasetMetadata.model_validate_json(uploaded_version.metadata_json) if uploaded_version else None
        return DatasetDetail(
            dataset=DatasetView.model_validate(dataset, from_attributes=True),
            selected_version=version_view(selected) if selected else None,
            latest_version_id=latest.id if latest else None,
            latest_run=run_view, assigned_rules=self._rule_view(assignment),
            rules_changed_since_run=changed,
            uploaded_at=datetime.fromisoformat(upload.created_at) if upload else None,
            uploaded_by=upload.actor if upload else None,
            source_filename=uploaded_metadata.original_filename if uploaded_metadata else None,
            source_format=uploaded_metadata.format if uploaded_metadata else None,
            recent_events=[AuditView.model_validate(event, from_attributes=True) for event in events],
            cell_review=self._cell_groups(selected, run_view, state) if selected else None,
            review_changed_since_run=state.review_changed, data_changed_since_run=state.data_changed,
            validation_pending=changed or state.review_changed or state.data_changed or old_scores or bool(run and run.processing_status == "failed"),
            resolved_identifier_column=identifier, identifier_reason=identifier_reason, ignored_cell_count=len(state.ignored),
        )

    def detail(self, dataset_id: str, version_id: str | None = None) -> DatasetDetail:
        with self.database.read() as session:
            return self._detail(session, require(session, Dataset, dataset_id), version_id)

    def upload_policy(self) -> UploadPolicy:
        return UploadPolicy(extensions=[f".{extension}" for extension in MEDIA_TYPES],
                            max_upload_bytes=self.settings.max_upload_bytes, max_rows=self.settings.max_rows,
                            max_columns=self.settings.max_columns, max_cells=self.settings.max_cells,
                            max_decoded_bytes=self.settings.max_decoded_bytes)

    def summaries(self, limit: int, offset: int) -> Page[DatasetDetail]:
        with self.database.read() as session:
            return page_of(session, select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id.desc()),
                           lambda row: self._detail(session, row), limit, offset)

    def revalidate(self, dataset_id: str, source_version_id: str) -> DatasetDetail:
        # The version and its pinned run are committed together under the database write lock.
        try:
            with self.database.write() as session:
                require(session, Dataset, dataset_id)
                source = self._selected_version(session, dataset_id, source_version_id)
                if source is None:
                    raise InputError("not_found", "The source version does not exist.", 404)
                latest = session.scalar(select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id)
                                        .order_by(DatasetVersion.number.desc()).limit(1))
                if source.dataset_id != dataset_id:
                    raise InputError("not_found", "The source version does not belong to this dataset.", 404)
                if latest is None or source.id != latest.id:
                    raise InputError("stale_version", "The dataset has a newer version. Refresh before revalidating.", 409)
                previous = self._latest_run(session, source.id)
                if previous and previous.processing_status == "running":
                    raise InputError("validation_running", "Wait for validation to finish.", 409)
                state = VersionReviewState.model_validate_json(source.review_state_json)
                detail = self._detail(session, require(session, Dataset, dataset_id), source.id)
                if not detail.validation_pending:
                    return detail
                # Edited/unvalidated versions and failed attempts reuse their source version.
                if state.data_changed or previous is None or previous.processing_status == "failed":
                    version = source
                else:
                    content = self.files.read(source.file_id, source.content_sha256)
                    metadata = DatasetMetadata.model_validate_json(source.metadata_json)
                    version = self.save_version(session, dataset_id, content,
                                                ParsedDataset(metadata=metadata, records=()), source, state)
                    self.audit(session, dataset_id, "version_revalidated", version.id)
                run = self.start_check(session, version)
        except Exception:
            try:
                self.reconcile()
            except Exception:
                logger.warning("File reconciliation deferred until storage is available")
            raise
        self.process_check(run.id)
        return self.detail(dataset_id, version.id)

    def apply_cell_review(self, dataset_id: str, request: CellReviewRequest) -> DatasetDetail:
        """Save an immediate edit or ignore, without running validation or requiring approval."""
        try:
            with self.database.write() as session:
                dataset = require(session, Dataset, dataset_id)
                source = self._selected_version(session, dataset_id, request.version)
                latest = self._selected_version(session, dataset_id, None)
                if source is None or latest is None or source.id != latest.id:
                    raise InputError("stale_version", "A newer version is available. Refresh before saving changes.", 409)
                run = self._latest_run(session, source.id)
                if run and run.processing_status == "running":
                    raise InputError("validation_running", "Wait for validation to finish before saving changes.", 409)
                state = VersionReviewState.model_validate_json(source.review_state_json)
                groups = self._cell_groups(source, self._run_view(session, run) if run else None, state)
                group = next((item for item in groups or [] if item.id == request.groupId), None)
                if group is None or not any(cell.rowNumber == request.rowNumber for cell in group.cells):
                    raise InputError("stale_finding", "This finding is no longer available. Refresh the review.", 409)
                numbers = {cell.rowNumber for cell in group.cells if request.scope == "all" or cell.rowNumber == request.rowNumber}
                parsed = self.parsed_version(source)
                row_ids = state.row_ids or list(range(1, len(parsed.records) + 1))
                column = parsed.metadata.headers.index(group.column)
                if any(cell_value(parsed.records[number - 1][column]) != group.currentValue for number in numbers):
                    raise InputError("stale_finding", "The flagged value has changed. Refresh the review.", 409)
                assignment = require(session, RuleSetRecord, dataset.rule_set_id or self.default_rule_set_id)
                rules, _ = resolved_rules(RuleSet.model_validate_json(assignment.configuration_json), parsed.metadata.headers)
                signatures = {rule.id: rule_signature(rule) for rule in rules.rules}
                action = request.action
                if action.type == "ignore":
                    def ignore_identity(item: IgnoredCell) -> tuple[int, str, str, str, str | None, str | None]:
                        return (item.row_id, item.column, item.kind, item.rule_id, item.value, item.signature)

                    decisions = {ignore_identity(item): item for item in state.ignored}
                    for number in sorted(numbers):
                        decision = IgnoredCell(row_id=row_ids[number - 1], column=group.column, kind=group.kind,
                            rule_id=group.ruleId, value=group.currentValue,
                            signature=signatures.get(group.ruleId) if group.kind == "violation" else None,
                            reason=action.reason.strip())
                        decisions[ignore_identity(decision)] = decision
                    state.ignored = list(decisions.values())
                    remaining_groups = []
                    for item in groups or []:
                        cells = [cell for cell in item.cells if item.id != group.id or cell.rowNumber not in numbers]
                        if cells:
                            remaining_groups.append(item.model_copy(update={"cells": cells}))
                    state.pending_groups = remaining_groups
                    state.review_changed = True
                    source.review_state_json = state.model_dump_json()
                    self.audit(session, dataset_id, "findings_ignored", source.id,
                        f"v{source.number} · {len(numbers)} finding(s) · {group.column} · {group.rule}"
                        + (" · " + action.reason.strip() if action.reason.strip() else ""))
                    saved_id = source.id
                else:
                    if action.type == "replace":
                        if action.value == group.currentValue:
                            raise InputError("no_changes", "Enter a value different from the current value.")
                        if request.scope == "all" and len(numbers) > 1 and any(
                            isinstance(rule, UniqueRule) and rule.column == group.column for rule in rules.rules
                        ):
                            raise InputError("bulk_unique_replacement", "Replace unique values one cell at a time.")
                    rows: list[tuple[str, ...]] = []
                    remaining_ids: list[int] = []
                    positions: dict[int, int] = {}
                    for number, row in enumerate(parsed.records, 1):
                        if number in numbers and action.type == "delete-row":
                            continue
                        if number in numbers and action.type == "replace":
                            row = tuple((action.value or "") if index == column else value for index, value in enumerate(row))
                        rows.append(row)
                        remaining_ids.append(row_ids[number - 1])
                        positions[number] = len(rows)
                    identifier, _ = identifier_column(rules, parsed.metadata.headers)
                    identifier_index = parsed.metadata.headers.index(identifier) if identifier is not None and identifier in parsed.metadata.headers else None
                    remaining_groups = []
                    for item in groups or []:
                        cells = []
                        for cell in item.cells:
                            if cell.rowNumber not in positions or (cell.rowNumber in numbers and item.column == group.column):
                                continue
                            position = positions[cell.rowNumber]
                            cells.append(ReviewedCell(rowNumber=position,
                                identifier=cell_value(rows[position - 1][identifier_index]) if identifier_index is not None else None))
                        if cells:
                            remaining_groups.append(item.model_copy(update={"cells": cells}))
                    state.row_ids = remaining_ids
                    state.pending_groups = remaining_groups
                    state.review_changed = True
                    state.data_changed = True
                    remaining = set(remaining_ids)
                    state.ignored = [decision for decision in state.ignored if decision.row_id in remaining]
                    # The UI downloads edited snapshots as CSV. Preserve the original upload in its immutable version.
                    buffer = io.StringIO(newline="")
                    writer = csv.writer(buffer, lineterminator="\r\n", quoting=csv.QUOTE_ALL)
                    writer.writerow(parsed.metadata.headers)
                    writer.writerows(rows)
                    content = ("\ufeff" + buffer.getvalue()).encode("utf-8")
                    filename = f"{dataset_id}_v{source.number + 1}.csv"
                    corrected = parse_dataset(content, filename, self.settings, allow_empty=True, internal_snapshot=True)
                    saved = self.save_version(session, dataset_id, content, corrected, source, state)
                    saved_id = saved.id
                    description = "row(s) deleted" if action.type == "delete-row" else "cell(s) updated in " + group.column
                    self.audit(session, dataset_id, "version_corrected", saved.id,
                               f"v{saved.number} · {len(numbers)} {description}")
        except Exception:
            try:
                self.reconcile()
            except Exception:
                logger.warning("File reconciliation deferred until storage is available")
            raise
        return self.detail(dataset_id, saved_id)

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
                           .order_by(CheckRun.created_at, run_order(), CheckRun.id),
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
                           .order_by(ReviewDecision.created_at, select(AuditEvent.sequence).where(
                               AuditEvent.entity_id == ReviewDecision.id,
                               AuditEvent.action == "review_added").scalar_subquery(), ReviewDecision.id),
                           lambda row: ReviewView.model_validate(row, from_attributes=True), limit, offset)

