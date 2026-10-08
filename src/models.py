from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String)


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_versions.id"))
    file_id: Mapped[str] = mapped_column(String(40), unique=True)
    content_sha256: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String)


class CheckRun(Base):
    __tablename__ = "check_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    processing_status: Mapped[str] = mapped_column(String)
    configuration_json: Mapped[str] = mapped_column(Text)
    settings_json: Mapped[str] = mapped_column(Text)
    reference_date: Mapped[str] = mapped_column(String)
    implementation_version: Mapped[str] = mapped_column(String)
    baseline_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_versions.id"))
    result_json: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    completed_at: Mapped[str | None] = mapped_column(String)


class FindingRecord(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    check_run_id: Mapped[str] = mapped_column(ForeignKey("check_runs.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("check_run_id", "position"),)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_dataset_sequence", "dataset_id", "sequence"),)

    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    action: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String(36))
    actor: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        CheckConstraint("decision IN ('needs_correction', 'accepted_as_is', 'dismissed')", name="valid_review_decision"),
        CheckConstraint("decision = 'needs_correction' OR (reason IS NOT NULL AND length(trim(reason)) > 0)", name="review_reason_required"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), index=True)
    decision: Mapped[str] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class Remediation(Base):
    __tablename__ = "remediations"
    __table_args__ = (
        CheckConstraint("status IN ('proposed', 'approved', 'rejected', 'executing', 'executed', 'failed')",
                        name="valid_remediation_status"),
        CheckConstraint("status != 'executed' OR (result_version_id IS NOT NULL AND check_run_id IS NOT NULL)",
                        name="executed_remediation_result"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    source_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    source_sha256: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    preview_token: Mapped[str | None] = mapped_column(String(32))
    previewed_at: Mapped[str | None] = mapped_column(String)
    decision_actor: Mapped[str | None] = mapped_column(String)
    decided_at: Mapped[str | None] = mapped_column(String)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    source_check_run_id: Mapped[str | None] = mapped_column(ForeignKey("check_runs.id"))
    result_version_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_versions.id"), unique=True)
    check_run_id: Mapped[str | None] = mapped_column(ForeignKey("check_runs.id"))
    executed_at: Mapped[str | None] = mapped_column(String)
    error_code: Mapped[str | None] = mapped_column(String)

