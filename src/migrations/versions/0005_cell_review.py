"""Persist cell identity/ignore state and pin it to each validation attempt."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("dataset_versions", "check_runs"):
        op.add_column(table, sa.Column("review_state_json", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("audit_events", sa.Column("description", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("audit_events", "description")
    for table in ("check_runs", "dataset_versions"):
        op.drop_column(table, "review_state_json")
