"""Create the current DataGuard schema for a new workspace."""
from alembic import op
import sqlalchemy as sa

revision = "0001_current"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("rule_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("rule_sets.id")),
        sa.Column("configuration_json", sa.Text, nullable=False),
        sa.Column("configuration_sha256", sa.String(64), nullable=False),
        sa.Column("actor", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.UniqueConstraint("name", "revision"))
    op.create_table("datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("rule_set_id", sa.String(36), sa.ForeignKey("rule_sets.id"), nullable=False))
    op.create_index("ix_datasets_rule_set_id", "datasets", ["rule_set_id"])
    op.create_table("dataset_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("dataset_versions.id")),
        sa.Column("file_id", sa.String(40), nullable=False, unique=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.Text, nullable=False),
        sa.Column("metadata_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("review_state_json", sa.Text, nullable=False, server_default="{}"),
        sa.UniqueConstraint("dataset_id", "number"))
    op.create_index("ix_dataset_versions_dataset_id", "dataset_versions", ["dataset_id"])
    op.create_table("check_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_id", sa.String(36), sa.ForeignKey("dataset_versions.id"), nullable=False),
        sa.Column("processing_status", sa.String, nullable=False),
        sa.Column("configuration_json", sa.Text, nullable=False),
        sa.Column("settings_json", sa.Text, nullable=False),
        sa.Column("reference_date", sa.String, nullable=False),
        sa.Column("implementation_version", sa.String, nullable=False),
        sa.Column("baseline_id", sa.String(36), sa.ForeignKey("dataset_versions.id")),
        sa.Column("result_json", sa.Text),
        sa.Column("error_code", sa.String),
        sa.Column("actor", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("completed_at", sa.String),
        sa.Column("rule_set_id", sa.String(36), sa.ForeignKey("rule_sets.id"), nullable=False),
        sa.Column("review_state_json", sa.Text, nullable=False, server_default="{}"))
    op.create_index("ix_check_runs_version_id", "check_runs", ["version_id"])
    op.create_index("ix_check_runs_rule_set_id", "check_runs", ["rule_set_id"])
    op.create_table("findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("check_run_id", sa.String(36), sa.ForeignKey("check_runs.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.UniqueConstraint("check_run_id", "position"))
    op.create_index("ix_findings_check_run_id", "findings", ["check_run_id"])
    op.create_table("audit_events",
        sa.Column("sequence", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("actor", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""))
    op.create_index("ix_audit_dataset_sequence", "audit_events", ["dataset_id", "sequence"])
    op.create_table("review_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id"), nullable=False),
        sa.Column("decision", sa.String, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("actor", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.CheckConstraint("decision IN ('needs_correction', 'accepted_as_is', 'dismissed')", name="valid_review_decision"),
        sa.CheckConstraint("decision = 'needs_correction' OR (reason IS NOT NULL AND length(trim(reason)) > 0)", name="review_reason_required"))
    op.create_index("ix_review_decisions_finding_id", "review_decisions", ["finding_id"])
    op.create_table("remediations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("source_version_id", sa.String(36), sa.ForeignKey("dataset_versions.id"), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("actor", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("preview_token", sa.String(32)),
        sa.Column("previewed_at", sa.String),
        sa.Column("decision_actor", sa.String),
        sa.Column("decided_at", sa.String),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("source_check_run_id", sa.String(36), sa.ForeignKey("check_runs.id")),
        sa.Column("result_version_id", sa.String(36), sa.ForeignKey("dataset_versions.id"), unique=True),
        sa.Column("check_run_id", sa.String(36), sa.ForeignKey("check_runs.id")),
        sa.Column("executed_at", sa.String),
        sa.Column("error_code", sa.String),
        sa.CheckConstraint("status IN ('proposed', 'approved', 'rejected', 'executing', 'executed', 'failed')",
                           name="valid_remediation_status"),
        sa.CheckConstraint("status != 'executed' OR (result_version_id IS NOT NULL AND check_run_id IS NOT NULL)",
                           name="executed_remediation_result"))
    op.create_index("ix_remediations_dataset_id", "remediations", ["dataset_id"])


def downgrade() -> None:
    for table in ("remediations", "review_decisions", "audit_events", "findings",
                  "check_runs", "dataset_versions", "datasets", "rule_sets"):
        op.drop_table(table)
