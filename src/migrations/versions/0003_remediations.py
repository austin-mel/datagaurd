from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.drop_table("remediations")
