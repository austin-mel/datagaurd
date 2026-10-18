from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from src.main import create_app
from src.settings import Settings


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
