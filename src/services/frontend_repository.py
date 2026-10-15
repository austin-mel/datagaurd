"""In-process counterpart of the frontend DatasetRepository. No HTTP routes or client wiring."""
from dataclasses import dataclass

from pydantic import JsonValue, ValidationError
from sqlalchemy import select

from src.errors import InputError
from src.models import Dataset, RuleSetRecord
from src.schemas import CellReviewRequest, DatasetDetail, DatasetMetadata, Metric
from src.rules import NumericRule, RuleSet
from src.services.catalog import Catalog, require
from src.services.cell_review import rule_type
from src.services.frontend_rules import EditorRuleset, backend_ruleset, editor_catalog, editor_ruleset
from src.services.identifiers import resolved_rules
from src.services.tabular import MEDIA_TYPES, parse_dataset

QUALITY_NOTE = ("Scores count each row once. Completeness: every cell present. Validity: no rule errors. "
                "Uniqueness: present, unique values in every enabled unique column. Overall is the mean of available scores.")
HISTORY_TITLES = {"version_uploaded": "Dataset uploaded", "check_completed": "Validation ran",
                  "rule_set_assigned": "Ruleset saved", "version_corrected": "Dataset edited", "findings_ignored": "Findings ignored"}


def dataset_to_frontend(detail: DatasetDetail) -> dict[str, JsonValue]:
    version, run = detail.selected_version, detail.latest_run
    result = run.result if run and run.processing_status == "completed" else None
    headers = version.metadata.headers if version else []
    score_compatible = bool(result and (result.metric_semantics == "row-based-v1"
        or result.implementation_version in {"tabular-validation/2.0.0", "tabular-validation/2.1.0"}))
    metrics = result.metrics if result and score_compatible else None
    dimensions: list[JsonValue] = []
    scores: list[float] = []
    for identity, label, attribute, description in (
        ("completeness", "Completeness", "completeness", "rows with no missing cells"),
        ("validity", "Validity", "valid_row_rate", "rows without rule errors"),
        ("uniqueness", "Uniqueness", "uniqueness", "rows unique in all tagged columns"),
    ):
        metric: Metric = getattr(metrics, attribute) if metrics else Metric()
        available = metric.status == "available"
        score = metric.percentage if available else None
        if score is not None:
            scores.append(score)
        dimensions.append({"id": identity, "label": label, "score": score, "passed": metric.numerator,
                           "total": metric.denominator, "description": description if available else metric.reason or "Not available"})
    findings = result.findings if result else []
    profiles: list[JsonValue] | None = None
    validation: JsonValue = None
    check_count = 0
    if result:
        effective, _ = resolved_rules(result.configuration, headers)
        visible_rules = {rule.id: rule for rule in effective.rules if not (isinstance(rule, NumericRule) and rule.generated_for)}
        # Match the editor's enabled checks, including checks with no nonmissing candidates.
        check_count = len(visible_rules)
        issues: list[JsonValue] = []
        for finding in findings:
            if finding.category != "validation":
                continue
            rule = visible_rules.get(finding.rule_id)
            if rule is None and finding.rule_id != result.configuration.structural_rule_id:
                continue
            issues.append({"id": finding.rule_id, "column": finding.column or "Dataset",
                           "rule": rule_type(rule) if rule else finding.rule_id,
                           "message": finding.explanation, "affectedRows": finding.affected_count})
        validation = {"checksRun": check_count, "issues": issues}
        profiles = []
        for profile in result.profile.columns:
            warnings = {number for finding in findings if finding.category == "statistical" and finding.column == profile.column
                        for number in finding.affected_record_numbers}
            summary: dict[str, JsonValue]
            if len(profile.observed_types) == 1 and profile.numeric_min is not None and profile.numeric_max is not None:
                summary = {"kind": "number-range", "minimum": profile.numeric_min, "maximum": profile.numeric_max}
            elif profile.observed_types == ["date"] and profile.date_min and profile.date_max:
                summary = {"kind": "date-range", "minimum": profile.date_min.isoformat(), "maximum": profile.date_max.isoformat()}
            else:
                summary = {"kind": "top-values", "values": [{"value": item.value, "count": item.count} for item in profile.top_categories]}
            profiles.append({"name": profile.column, "observedTypes": list(profile.observed_types),
                             "missingCount": profile.missing_count, "warningCount": len(warnings),
                             "uniqueCount": profile.distinct_count, "summary": summary})
    status = (run.processing_status if run and run.processing_status in {"running", "failed"} else
              "unvalidated" if result is None else "needs-review" if findings else "healthy" if check_count else "unvalidated")
    quality_note = QUALITY_NOTE if result else "Validation results are not available."
    if result and not score_compatible:
        quality_note = "Run validation to calculate row-based quality scores."
    if detail.data_changed_since_run:
        quality_note = "Data changed. Run validation to calculate profiles, issues, and quality scores."
    elif detail.ignored_cell_count:
        quality_note += " Ignored rule findings are excluded from error counts; completeness still reflects actual missing cells."
    global_warnings = [finding.explanation for finding in findings if finding.category != "validation" and not finding.affected_record_numbers]
    if global_warnings:
        quality_note += " Dataset warnings: " + " ".join(dict.fromkeys(global_warnings))
    document: dict[str, JsonValue] = {
        "id": detail.dataset.id, "name": detail.dataset.name,
        "source": (detail.source_format or (version.metadata.format if version else "file")).upper() + " upload",
        "sourceIcon": "file", "rowCount": version.metadata.row_count if version else 0,
        "columns": list(headers), "version": f"v{version.number}" if version else "Not available",
        "isCurrentVersion": bool(version and version.id == detail.latest_version_id),
        "status": status, "processingStatus": run.processing_status if run else "not_started",
        "lastValidatedAt": result.checked_at.isoformat() if result else None,
        "rulesChangedSinceRun": detail.rules_changed_since_run,
        "reviewChangedSinceRun": detail.review_changed_since_run,
        "validationPending": detail.validation_pending,
        "dataChangedSinceRun": detail.data_changed_since_run,
        "quality": sum(scores) / len(scores) if scores else None,
        "qualityDimensions": dimensions, "qualityNote": quality_note, "columnProfiles": profiles,
        "validation": validation,
        "cellReview": [group.model_dump(mode="json") for group in detail.cell_review] if detail.cell_review is not None else None,
        "ruleset": editor_ruleset(detail.assigned_rules, headers).model_dump(mode="json", exclude_none=True),
        "history": [{"id": str(event.sequence), "occurredAt": event.created_at.isoformat(),
                     "title": HISTORY_TITLES[event.action], "description": event.description or event.actor}
                    for event in detail.recent_events if event.action in HISTORY_TITLES],
    }
    if version:
        document.update(versionId=version.id, filename=detail.source_filename or version.metadata.original_filename,
                        downloadFilename=f"{detail.dataset.id}_v{version.number}.{version.metadata.format}")
    if run:
        document["latestRunId"] = run.id
        if run.error_code:
            document["processingError"] = run.error_code
    if detail.uploaded_at:
        document["uploadedAt"] = detail.uploaded_at.isoformat()
    if detail.uploaded_by:
        document["uploadedBy"] = detail.uploaded_by
    return document


@dataclass(frozen=True)
class DatasetDownload:
    filename: str
    content: bytes
    media_type: str


class FrontendRepository:
    """Synchronous service boundary, ready for a future transport adapter.

    Reads return the frontend's camelCase Dataset/Workspace shape. No list is silently
    truncated. Version arguments accept the UI's vN labels as well as backend UUIDs.
    """

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    @property
    def source(self) -> dict[str, str]:
        # Matches the UI's live-backend discriminator; this class itself has no transport.
        return {"kind": "api"}

    def getWorkspace(self) -> dict[str, JsonValue]:
        with self.catalog.database.read() as session:
            datasets: list[JsonValue] = [dataset_to_frontend(self.catalog._detail(session, dataset))
                for dataset in session.scalars(select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id.desc()))]
        return {"datasets": datasets, "ruleCatalog": editor_catalog()}

    def getDataset(self, datasetId: str, version: str | None = None) -> dict[str, JsonValue]:
        return dataset_to_frontend(self.catalog.detail(datasetId, version))

    def getUploadPolicy(self) -> dict[str, JsonValue]:
        return self.catalog.upload_policy().model_dump(mode="json")

    def upload(self, content: bytes, filename: str, *, sheetName: str | None = None,
               datasetId: str | None = None, contentType: str | None = None) -> dict[str, JsonValue]:
        parsed = parse_dataset(content, filename, self.catalog.settings, contentType, sheetName)
        uploaded = self.catalog.upload(content, parsed, datasetId)
        return self.getDataset(uploaded.dataset.id, uploaded.version.id)

    def download(self, datasetId: str, version: str) -> DatasetDownload:
        with self.catalog.database.read() as session:
            selected = self.catalog._selected_version(session, datasetId, version)
            if selected is None:
                raise InputError("not_found", "Dataset version not found.", 404)
            metadata = DatasetMetadata.model_validate_json(selected.metadata_json)
            content = self.catalog.files.read(selected.file_id, selected.content_sha256)
            return DatasetDownload(f"{datasetId}_v{selected.number}.{metadata.format}", content, MEDIA_TYPES[metadata.format])

    def updateRuleset(self, datasetId: str, ruleset: EditorRuleset | dict[str, JsonValue]) -> dict[str, JsonValue]:
        try:
            editor = EditorRuleset.model_validate(ruleset)
            with self.catalog.database.write() as session:
                dataset = require(session, Dataset, datasetId)
                version = self.catalog._selected_version(session, datasetId, None)
                if version is None:
                    raise InputError("not_found", "Upload a dataset before assigning rules.", 404)
                run = self.catalog._latest_run(session, version.id)
                if run and run.processing_status == "running":
                    raise InputError("validation_running", "Wait for validation to finish before saving rules.", 409)
                headers = DatasetMetadata.model_validate_json(version.metadata_json).headers
                assignment = require(session, RuleSetRecord, dataset.rule_set_id or self.catalog.default_rule_set_id)
                assigned_rules = RuleSet.model_validate_json(assignment.configuration_json)
                rules = backend_ruleset(editor, assigned_rules, headers)
                # Creating a custom copy must not deduplicate back to the read-only default.
                unchanged = rules.model_dump(mode="json") == assigned_rules.model_dump(mode="json")
                saved = assignment if unchanged and assignment.id != self.catalog.default_rule_set_id else self.catalog._register_rules(session, rules)
                if dataset.rule_set_id != saved.id:
                    dataset.rule_set_id = saved.id
                    count = sum(not (isinstance(rule, NumericRule) and rule.generated_for) for rule in rules.rules)
                    self.catalog.audit(session, datasetId, "rule_set_assigned", saved.id,
                                       f"{rules.name} · {count} rule(s) saved.")
        except ValidationError as exc:
            raise InputError("invalid_rules", "Every rule must be valid, complete and defined, including disabled rules.",
                             details={"errors": str(exc)}) from exc
        return self.getDataset(datasetId)

    def revalidate(self, datasetId: str, version: str) -> dict[str, JsonValue]:
        return dataset_to_frontend(self.catalog.revalidate(datasetId, version))

    def applyCellReview(self, datasetId: str, request: CellReviewRequest | dict[str, JsonValue]) -> dict[str, JsonValue]:
        parsed = CellReviewRequest.model_validate(request)
        return dataset_to_frontend(self.catalog.apply_cell_review(datasetId, parsed))
