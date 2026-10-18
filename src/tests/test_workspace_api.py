from fastapi.testclient import TestClient
from typing import Any

from src.main import create_app
from src.settings import PROJECT_ROOT, Settings


def test_workspace_lifecycle(settings: Settings) -> None:
    settings = settings.model_copy(update={'rules_path': PROJECT_ROOT / 'config' / 'generic.yaml'})
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/v1/workspace').json()['datasets'] == []
        policy = client.get('/api/v1/upload-policy').json()
        assert '.csv' in policy['extensions']
        source = b'id,amount\n1,5\n1,10\n3,15\n'
        response = client.post('/api/v1/datasets', files={'file': ('sample.csv', source, 'text/csv')})
        assert response.status_code == 201, response.text
        dataset = response.json()
        identity = dataset['id']
        path = '/api/v1/datasets/' + identity
        assert dataset['rowCount'] == 3
        assert len(dataset['columnProfiles']) == 2
        assert all(dimension['score'] is not None for dimension in dataset['qualityDimensions'])
        assert dataset['uploadedBy'] == settings.actor
        assert dataset['history'] and dataset['cellReview'] and dataset['validation']['issues']
        assert client.get('/api/v1/workspace').json()['datasets'] == [dataset]
        download = client.get(path + '/file', params={'version': dataset['version']})
        assert download.content == source
        assert 'attachment' in download.headers['content-disposition']
        group = dataset['cellReview'][0]
        reviewed = client.post(path + '/cell-reviews', json={
            'version': dataset['version'], 'groupId': group['id'], 'rowNumber': group['cells'][0]['rowNumber'],
            'scope': 'one', 'action': {'type': 'replace', 'value': '2'},
        })
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()['dataChangedSinceRun']
        validated = client.post(path + '/validation', json={'version': reviewed.json()['version']})
        assert validated.status_code == 200, validated.text
        assert validated.json()['processingStatus'] == 'completed'
        assert not validated.json()['validationPending']
        rules = validated.json()['ruleset']
        rules.update(kind='custom', name='Custom API rules')
        saved = client.put(path + '/ruleset', json=rules)
        assert saved.status_code == 200, saved.text
        assert client.get(path).json()['ruleset']['name'] == 'Custom API rules'
        assert client.post(path + '/validation', json={'version': 'v1'}).status_code == 409
        assert client.get(path + '/file', params={'version': 'v1'}).content == source
        assert client.get('/api/v1/datasets/missing').status_code == 404
        assert client.post(path + '/validation', json={}).status_code == 422
        assert client.post('/api/v1/datasets', files={'file': ('bad.exe', b'bad')}).status_code == 415
    # Confirm metadata and edits survive a restart.
    with TestClient(create_app(settings)) as client:
        assert client.get(path).json()['ruleset']['name'] == 'Custom API rules'


def test_allowed_cors_origins(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.options('/api/v1/workspace', headers={
            'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'GET',
        })
        assert response.status_code == 200
        assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
        response = client.options('/api/v1/workspace', headers={
            'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'GET',
        })
        assert response.status_code == 400


def test_legacy_upgrade_pins_recorded_cutoff() -> None:
    from src.scripts.migrate_legacy_rules import upgrade
    legacy: dict[str, Any] = {'schema_version': 1, 'name': 'Legacy', 'structural_rule_id': 'COLUMNS',
              'required_columns': ['day'], 'rules': [
                  {'id': 'DATE_PARSE', 'column': 'day', 'kind': 'date', 'formats': ['%Y-%m-%d'], 'explanation': 'Valid date'},
                  {'id': 'DATE_FUTURE', 'column': 'day', 'kind': 'not_future', 'latest': 'today',
                   'prerequisite': 'DATE_PARSE', 'explanation': 'No future dates'},
              ]}
    converted = upgrade(legacy, '2026-10-07').model_dump()
    assert converted['rules'][0]['date'] == '9999-12-31'
    assert converted['rules'][1]['date'] == '2026-10-07'
    assert legacy['rules'][0]['kind'] == 'date'


def test_numeric_profiles_include_integer_and_decimal_values(settings: Settings) -> None:
    settings = settings.model_copy(update={'rules_path': PROJECT_ROOT / 'config' / 'generic.yaml'})
    with TestClient(create_app(settings)) as client:
        result = client.post('/api/v1/datasets', files={'file': ('prices.csv', b'id,price\nA,1\nB,2.5\n', 'text/csv')})
        assert result.status_code == 201
        assert result.json()['columnProfiles'][1]['summary'] == {'kind': 'number-range', 'minimum': 1.0, 'maximum': 2.5}
