from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
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
    for table in ("datasets", "check_runs"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN rule_set_id VARCHAR(36) REFERENCES rule_sets(id)")
        op.create_index(f"ix_{table}_rule_set_id", table, ["rule_set_id"])


def downgrade() -> None:
    for table in ("check_runs", "datasets"):
        op.drop_index(f"ix_{table}_rule_set_id", table)
        op.drop_column(table, "rule_set_id")
    op.drop_table("rule_sets")
