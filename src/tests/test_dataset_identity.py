from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from src.main import create_app
from src.models import Dataset, DatasetVersion, AuditEvent
from src.rules import load_rules
from src.services.catalog import Catalog, now
from src.services.tabular import parse_dataset
from src.settings import PROJECT_ROOT, Settings


def test_duplicate_filenames_have_independent_uuid_primary_keys(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / 'storage')
    with TestClient(create_app(settings)) as client:
        first_bytes = b'id,value\n1,first\n'
        second_bytes = b'id,value\n1,second\n2,another\n'
        first = client.post('/api/v1/datasets', files={'file': ('same.csv', first_bytes, 'text/csv')}).json()
        second = client.post('/api/v1/datasets', files={'file': ('same.csv', second_bytes, 'text/csv')}).json()
        assert first['name'] == second['name'] == 'same.csv'
        assert str(UUID(first['id'])) == first['id']
        assert str(UUID(second['id'])) == second['id']
        assert first['id'] != second['id']
        assert len(client.get('/api/v1/workspace').json()['datasets']) == 2
        for dataset, content, count in [(first, first_bytes, 1), (second, second_bytes, 2)]:
            route = '/api/v1/datasets/' + dataset['id']
            assert client.get(route).json()['rowCount'] == count
            assert client.get(route + '/file', params={'version': 'v1'}).content == content
        rules = first['ruleset']
        rules.update(kind='custom', name='Only first dataset')
        assert client.put('/api/v1/datasets/' + first['id'] + '/ruleset', json=rules).status_code == 200
        assert client.get('/api/v1/datasets/' + second['id']).json()['ruleset']['kind'] == 'default'
    with TestClient(create_app(settings)) as client:
        assert {item['id'] for item in client.get('/api/v1/workspace').json()['datasets']} == {first['id'], second['id']}


def test_uuid_migration_preserves_versions_files_checks_and_audit(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / 'storage')
    catalog = Catalog(settings, load_rules(settings.rules_path))
    catalog.initialize()
    original = b'id,value\n1,original\n'
    try:
        with catalog.database.engine.begin() as connection:
            config = Config(str(PROJECT_ROOT / 'alembic.ini'))
            config.attributes['connection'] = connection
            command.downgrade(config, '0005')
        with catalog.database.write() as session:
            session.add(Dataset(id='demo-facilities', name='same.csv', created_at=now(), rule_set_id=catalog.default_rule_set_id))
            session.flush()
            catalog.audit(session, 'demo-facilities', 'dataset_created', 'demo-facilities')
        saved = catalog.upload(original, parse_dataset(original, 'same.csv', settings), 'demo-facilities')
        existing = catalog.upload(original, parse_dataset(original, 'same.csv', settings))
        before = catalog.detail('demo-facilities')
        catalog.initialize()
        identity = '3be295a2-aad7-4724-9853-44729e762066'
        after = catalog.detail(identity)
        assert after.dataset.name == before.dataset.name
        assert after.latest_run == before.latest_run
        assert after.recent_events == [event.model_copy(update={'dataset_id': identity}) for event in before.recent_events]
        assert after.selected_version and after.selected_version.id == saved.version.id
        assert catalog.version_content(saved.version.id)[0] == original
        assert catalog.dataset(existing.dataset.id) == existing.dataset
        with catalog.database.read() as session:
            assert session.get(Dataset, 'demo-facilities') is None
            version = session.get(DatasetVersion, saved.version.id)
            assert version and version.dataset_id == identity
            assert session.scalar(select(AuditEvent.entity_id).where(AuditEvent.action == 'dataset_created', AuditEvent.dataset_id == identity)) == identity
            assert session.execute(text('PRAGMA foreign_key_check')).all() == []
        catalog.initialize()
        assert catalog.datasets(100, 0).total == 2
    finally:
        catalog.database.close()
