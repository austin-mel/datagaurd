from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("review_decisions")

