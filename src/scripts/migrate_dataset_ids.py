"""Back up the local metadata database and apply the UUID primary-key migration."""
import json
import sqlite3
from uuid import UUID, uuid4

from src.database import Database
from src.settings import Settings


def main() -> None:
    database = Database(Settings().storage_dir)
    path = database.directory / 'metadata.sqlite3'
    backup: str | None = None
    before: dict[str, int] = {}
    if path.exists():
        backup_path = database.directory / f'metadata-before-uuid-{uuid4().hex}.sqlite3'
        with sqlite3.connect(path) as source, sqlite3.connect(backup_path) as target:
            source.backup(target)
            for table in ('datasets', 'dataset_versions', 'check_runs', 'audit_events', 'remediations'):
                before[table] = source.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
        backup = str(backup_path)
    try:
        database.initialize()
        with sqlite3.connect(path) as connection:
            identities = [row[0] for row in connection.execute('SELECT id FROM datasets')]
            for identity in identities:
                UUID(identity)
            for table, count in before.items():
                if connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0] != count:
                    raise RuntimeError(f'Record count changed for {table}')
            if connection.execute('PRAGMA foreign_key_check').fetchall():
                raise RuntimeError('Foreign-key verification failed')
        print(json.dumps({'backup': backup, 'dataset_ids': identities, 'record_counts_preserved': before}, indent=2))
    finally:
        database.close()


if __name__ == '__main__':
    main()
