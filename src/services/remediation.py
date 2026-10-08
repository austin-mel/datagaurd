import csv
import io
import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.errors import InputError
from src.models import CheckRun, Dataset, DatasetVersion, Remediation
from src.schemas import (
    ApprovalRequest, ExecutionResponse, Metric, MetricChanges, Page, RecordChange,
    RejectionRequest, RemediationComparison, RemediationPreview, RemediationRequest, RemediationView,
)
from src.services.catalog import Catalog, now, page_of, require, version_view
from src.services.csv_parser import ParsedCsv, parse_csv

logger = logging.getLogger("dataguard")
TRANSITIONS = {
    "proposed": {"approved", "rejected"},
    "approved": {"executing"},
    "executing": {"executed", "failed"},
}


def proposal(row: Remediation) -> RemediationRequest:
    return RemediationRequest.model_validate_json(row.payload_json)


def remediation_view(row: Remediation) -> RemediationView:
    request = proposal(row)
    return RemediationView(
        id=row.id, dataset_id=row.dataset_id, source_version_id=row.source_version_id,
        source_sha256=row.source_sha256, column=request.column, replacement=request.replacement,
        reason=request.reason, selected_count=len(request.records),
        changed_count=sum(record.expected_value != request.replacement for record in request.records),
        status=row.status, actor=row.actor, created_at=datetime.fromisoformat(row.created_at),
        previewed_at=datetime.fromisoformat(row.previewed_at) if row.previewed_at else None,
        decision_actor=row.decision_actor,
        decided_at=datetime.fromisoformat(row.decided_at) if row.decided_at else None,
        rejection_reason=row.rejection_reason, source_check_run_id=row.source_check_run_id,
        result_version_id=row.result_version_id, check_run_id=row.check_run_id,
        executed_at=datetime.fromisoformat(row.executed_at) if row.executed_at else None,
        error_code=row.error_code,
    )


def change_page(request: RemediationRequest, limit: int, offset: int) -> Page[RecordChange]:
    return Page(items=[RecordChange(record_number=record.record_number, old_value=record.expected_value,
                                   new_value=request.replacement, changed=record.expected_value != request.replacement)
                       for record in request.records[offset:offset + limit]],
                total=len(request.records), limit=limit, offset=offset)


def metric_delta(before: Metric, after: Metric) -> float | None:
    if before.percentage is None or after.percentage is None:
        return None
    return after.percentage - before.percentage


class Remediations:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    def _source(self, session: Session, request: RemediationRequest) -> tuple[DatasetVersion, ParsedCsv]:
        version = require(session, DatasetVersion, request.source_version_id)
        latest = session.scalar(select(DatasetVersion.id).where(DatasetVersion.dataset_id == version.dataset_id)
                                .order_by(DatasetVersion.number.desc()).limit(1))
        if latest != version.id:
            raise InputError("stale_source", "Propose a correction against the latest dataset version.", 409)
        if version.content_sha256 != request.source_sha256:
            raise InputError("source_hash_mismatch", "The source hash does not match this version.", 409)
        parsed = self.catalog.parsed_version(version)
        if request.column not in parsed.metadata.headers:
            raise InputError("unknown_column", "The selected column does not exist.")
        if len(request.records) > self.catalog.settings.max_rows:
            raise InputError("too_many_records", "The proposal exceeds the configured record limit.", 413)
        column = parsed.metadata.headers.index(request.column)
        for record in request.records:
            if record.record_number > len(parsed.records):
                raise InputError("unknown_record", "A selected record does not exist.",
                                 details={"record_number": record.record_number})
            if parsed.records[record.record_number - 1][column] != record.expected_value:
                raise InputError("old_value_mismatch", "A selected record does not contain its expected old value.",
                                 409, {"record_number": record.record_number})
        if all(record.expected_value == request.replacement for record in request.records):
            raise InputError("no_changes", "The replacement would not change any selected record.")
        return version, parsed

    def _require_status(self, row: Remediation, status: str) -> None:
        if row.status != status:
            raise InputError("invalid_transition", f"This action requires a {status} proposal.", 409,
                             {"status": row.status})

    def _transition(self, session: Session, row: Remediation, status: str) -> None:
        if status not in TRANSITIONS.get(row.status, set()):
            raise InputError("invalid_transition", "The proposal cannot enter this state.", 409)
        row.status = status
        self.catalog.audit(session, row.dataset_id, f"remediation_{status}", row.id)
        session.flush()

    def create(self, request: RemediationRequest) -> RemediationView:
        request = request.model_copy(update={"records": sorted(request.records, key=lambda record: record.record_number)})
        with self.catalog.database.write() as session:
            source, _ = self._source(session, request)
            row = Remediation(id=str(uuid4()), dataset_id=source.dataset_id, source_version_id=source.id,
                              source_sha256=source.content_sha256, payload_json=request.model_dump_json(),
                              status="proposed", actor=self.catalog.settings.actor, created_at=now())
            session.add(row)
            self.catalog.audit(session, source.dataset_id, "remediation_proposed", row.id)
        return remediation_view(row)

    def get(self, remediation_id: str) -> RemediationView:
        with self.catalog.database.read() as session:
            return remediation_view(require(session, Remediation, remediation_id))

    def list(self, dataset_id: str, limit: int, offset: int) -> Page[RemediationView]:
        with self.catalog.database.read() as session:
            require(session, Dataset, dataset_id)
            return page_of(session, select(Remediation).where(Remediation.dataset_id == dataset_id)
                           .order_by(Remediation.created_at, Remediation.id), remediation_view, limit, offset)

    def records(self, remediation_id: str, limit: int, offset: int) -> Page[RecordChange]:
        with self.catalog.database.read() as session:
            return change_page(proposal(require(session, Remediation, remediation_id)), limit, offset)

    def preview(self, remediation_id: str) -> RemediationPreview:
        with self.catalog.database.write() as session:
            row = require(session, Remediation, remediation_id)
            self._require_status(row, "proposed")
            request = proposal(row)
            self._source(session, request)
            token = uuid4().hex
            row.preview_token = token
            row.previewed_at = now()
            self.catalog.audit(session, row.dataset_id, "remediation_previewed", row.id)
        return RemediationPreview(remediation=remediation_view(row), preview_token=token,
                                  samples=change_page(request, self.catalog.settings.finding_sample_size, 0).items)

    def approve(self, remediation_id: str, request: ApprovalRequest) -> RemediationView:
        with self.catalog.database.write() as session:
            row = require(session, Remediation, remediation_id)
            self._require_status(row, "proposed")
            if row.preview_token is None or row.preview_token != request.preview_token:
                raise InputError("preview_required", "Approval requires the latest preview token.", 409)
            self._source(session, proposal(row))
            row.decision_actor = self.catalog.settings.actor
            row.decided_at = now()
            self._transition(session, row, "approved")
        return remediation_view(row)

    def reject(self, remediation_id: str, request: RejectionRequest) -> RemediationView:
        with self.catalog.database.write() as session:
            row = require(session, Remediation, remediation_id)
            self._require_status(row, "proposed")
            row.rejection_reason = request.reason
            row.decision_actor = self.catalog.settings.actor
            row.decided_at = now()
            self._transition(session, row, "rejected")
        return remediation_view(row)

    def _replace(self, parsed: ParsedCsv, request: RemediationRequest) -> tuple[bytes, ParsedCsv]:
        selected = {record.record_number for record in request.records}
        column = parsed.metadata.headers.index(request.column)
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\r\n")
        writer.writerow(parsed.metadata.headers)
        for number, values in enumerate(parsed.records, start=1):
            row = list(values)
            if number in selected:
                row[column] = request.replacement
            writer.writerow(row)
            if buffer.tell() > self.catalog.settings.max_upload_bytes:
                raise InputError("upload_too_large", "The corrected CSV exceeds the configured size limit.", 413)
        content = buffer.getvalue().encode("utf-8")
        return content, parse_csv(content, parsed.metadata.original_filename, self.catalog.settings)

    def _record_failure(self, remediation_id: str, error: Exception) -> bool:
        with self.catalog.database.write() as session:
            row = require(session, Remediation, remediation_id)
            if row.status == "executed":
                return True
            if row.status == "approved":
                self._transition(session, row, "executing")
                row.error_code = error.code if isinstance(error, InputError) else "execution_failed"
                self._transition(session, row, "failed")
        return False

    def execute(self, remediation_id: str) -> ExecutionResponse:
        attempted = False
        try:
            with self.catalog.database.write() as session:
                row = require(session, Remediation, remediation_id)
                if row.status != "executed":
                    self._require_status(row, "approved")
                    request = proposal(row)
                    source, parsed = self._source(session, request)
                    attempted = True
                    self._transition(session, row, "executing")
                    content, corrected = self._replace(parsed, request)
                    before = session.scalar(select(CheckRun).where(CheckRun.version_id == source.id)
                                            .order_by(CheckRun.created_at.desc(), CheckRun.id.desc()).limit(1))
                    row.source_check_run_id = before.id if before else None
                    version = self.catalog.save_version(session, row.dataset_id, content, corrected, source)
                    self.catalog.audit(session, row.dataset_id, "version_corrected", version.id)
                    run = self.catalog.start_check(session, version)
                    row.result_version_id = version.id
                    row.check_run_id = run.id
                    row.executed_at = now()
                    self._transition(session, row, "executed")
        except Exception as exc:
            if not attempted:
                raise
            try:
                committed = self._record_failure(remediation_id, exc)
            finally:
                try:
                    self.catalog.reconcile()
                except Exception:
                    logger.warning("Correction file reconciliation deferred until storage is available")
            if not committed:
                if isinstance(exc, InputError):
                    raise
                raise InputError("execution_failed", "The correction could not be saved. Retrieve its status before retrying.",
                                 503, {"remediation_id": remediation_id}) from exc
        return self._execution_result(remediation_id)

    def _execution_result(self, remediation_id: str) -> ExecutionResponse:
        row = self.get(remediation_id)
        if row.result_version_id is None or row.check_run_id is None:
            raise InputError("result_unavailable", "The correction has no saved result.", 409)
        try:
            run = self.catalog.process_check(row.check_run_id)
            version = self.catalog.version(row.result_version_id)
        except Exception as exc:
            raise InputError("analysis_unavailable", "The correction was saved. Retry execution to resume its check, "
                             "or create a new check for the saved version.", 503,
                             {"remediation_id": row.id, "version_id": row.result_version_id,
                              "check_run_id": row.check_run_id}) from exc
        return ExecutionResponse(remediation=row, version=version, check_run=run)

    def compare(self, remediation_id: str, limit: int, offset: int) -> RemediationComparison:
        with self.catalog.database.read() as session:
            row = require(session, Remediation, remediation_id)
            self._require_status(row, "executed")
            if row.result_version_id is None or row.check_run_id is None:
                raise InputError("result_unavailable", "The correction has no saved result.", 409)
            source = require(session, DatasetVersion, row.source_version_id)
            version = require(session, DatasetVersion, row.result_version_id)
            before = self.catalog._run_view(session, require(session, CheckRun, row.source_check_run_id)) if row.source_check_run_id else None
            latest = session.scalar(select(CheckRun).where(CheckRun.version_id == version.id)
                                    .order_by(CheckRun.created_at.desc(), CheckRun.id.desc()).limit(1))
            after = self.catalog._run_view(session, latest or require(session, CheckRun, row.check_run_id))
            comparable = bool(before and before.result and after.result
                              and before.configuration == after.configuration
                              and before.settings_snapshot == after.settings_snapshot
                              and before.reference_date == after.reference_date
                              and before.implementation_version == after.implementation_version)
            changes = MetricChanges()
            if comparable and before and before.result and after.result:
                old, new = before.result.metrics, after.result.metrics
                changes = MetricChanges(completeness=metric_delta(old.completeness, new.completeness),
                                        valid_row_rate=metric_delta(old.valid_row_rate, new.valid_row_rate),
                                        duplicate_id_rate=metric_delta(old.duplicate_id_rate, new.duplicate_id_rate))
            return RemediationComparison(
                remediation=remediation_view(row), before_version=version_view(source), after_version=version_view(version),
                before_check_run=before, after_check_run=after, checks_comparable=comparable,
                comparison_reason=None if comparable else "Both runs must be completed with matching rules, settings, reference date and implementation.",
                metric_change_percentage_points=changes, changes=change_page(proposal(row), limit, offset),
            )
