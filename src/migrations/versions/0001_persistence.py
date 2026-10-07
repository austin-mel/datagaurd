from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.String, nullable=False))
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
        sa.Column("completed_at", sa.String))
    op.create_index("ix_check_runs_version_id", "check_runs", ["version_id"])
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
        sa.Column("created_at", sa.String, nullable=False))
    op.create_index("ix_audit_dataset_sequence", "audit_events", ["dataset_id", "sequence"])


def downgrade() -> None:
    for table in ["audit_events", "findings", "check_runs", "dataset_versions", "datasets"]:
        op.drop_table(table)

