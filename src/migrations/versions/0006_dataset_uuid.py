"""Use UUIDs as the existing dataset primary key; preserve related records."""
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

DEMO_IDS = {
    'demo-facilities': '3be295a2-aad7-4724-9853-44729e762066',
    'demo-customers': '9e716851-5f95-4433-b771-d336b0d00d20',
    'demo-inventory': '8e6483be-d006-4ab9-84c8-e86eac26b997',
}


def upgrade() -> None:
    connection = op.get_bind()
    # Insert the new parent before moving children, keeping foreign keys enabled.
    # A savepoint makes the data remap atomic even on SQLite's non-DDL migrations.
    with connection.begin_nested():
        identities: list[str] = list(connection.execute(sa.text('SELECT id FROM datasets')).scalars())
        for old_id in identities:
            try:
                UUID(old_id)
                continue
            except ValueError:
                pass
            new_id = DEMO_IDS.get(old_id) or str(uuid4())
            parameters = {'old': old_id, 'new': new_id}
            # A collision fails/rolls back instead of merging distinct datasets.
            connection.execute(sa.text('INSERT INTO datasets (id, name, created_at, rule_set_id) '
                'SELECT :new, name, created_at, rule_set_id FROM datasets WHERE id = :old'), parameters)
            for table in ('dataset_versions', 'audit_events', 'remediations'):
                connection.execute(sa.text(f'UPDATE {table} SET dataset_id = :new WHERE dataset_id = :old'), parameters)
            connection.execute(sa.text('UPDATE audit_events SET entity_id = :new WHERE entity_id = :old'), parameters)
            connection.execute(sa.text('DELETE FROM datasets WHERE id = :old'), parameters)


def downgrade() -> None:
    # Data-only migration: keep valid UUIDs and references when downgrading code.
    pass
