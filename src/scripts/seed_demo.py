"""Idempotent, explicit demo seeding. Never runs automatically in production."""
import csv
import io
import json
from collections.abc import Iterator
from typing import Any
from uuid import UUID

from src.models import Dataset
from src.rules import RuleSet, load_rules
from src.services.catalog import Catalog
from src.services.tabular import parse_dataset
from src.settings import PROJECT_ROOT, Settings

COUNTRIES = ['Mexico', 'United Kingdom', 'France', 'Germany', 'Italy', 'Spain', 'Portugal',
             'Netherlands', 'Belgium', 'Sweden', 'Norway', 'Denmark', 'Finland', 'Ireland',
             'Switzerland', 'Austria', 'Poland', 'Australia', 'New Zealand', 'Japan',
             'South Korea', 'India', 'Singapore', 'Brazil', 'Argentina', 'South Africa']


def customers(count: int) -> Iterator[dict[str, str | None]]:
    for index in range(count):
        identity, email = index - 1243, index - 2100
        yield {
            'customer_id': None if identity < 0 else 'CUS-001204' if identity < 3 else
                f'CUS-DUP-{(identity - 3) // 2}' if identity < 9643 else f'CUS-UNQ-{identity}',
            'customer_name': 'Alex Lee' if index < 12 else f'Customer group {(index - 12) // 2}' if index < 7214 else f'Customer {index}',
            'email': None if email < 0 else 'contact@example.com' if email < 8 else
                f'group{(email - 8) // 2}@example.com' if email < 3198 else
                f'invalid-email-{email}' if email < 3898 else f'customer{email}@example.com',
            'country': None if index < 45 else 'United States' if index < 176477 else 'Canada' if index < 207797 else COUNTRIES[(index - 207797) % len(COUNTRIES)],
        }


def seed_demo(catalog: Catalog) -> list[dict[str, Any]]:
    manifest = json.loads((PROJECT_ROOT / 'config' / 'demo-datasets.json').read_text(encoding='utf-8'))
    output: list[dict[str, Any]] = []
    for spec in manifest:
        # Stable IDs avoid duplicate datasets on reruns; existing demo edits are preserved.
        identity = str(UUID(spec['id']))
        with catalog.database.read() as session:
            existing = session.get(Dataset, identity)
        if existing and catalog.detail(identity).selected_version:
            detail = catalog.detail(identity)
            if detail.latest_run and detail.latest_run.processing_status == 'failed' and detail.selected_version:
                catalog.check(detail.selected_version.id)
            output.append({'id': identity, 'created': False})
            continue
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=spec['columns'], lineterminator='\n')
        writer.writeheader()
        rows = customers(spec['row_count']) if spec.get('generator') == 'customers-v1' else spec['rows']
        writer.writerows(rows)
        content = stream.getvalue().encode('utf-8')
        assignment = catalog.create_rule_set(RuleSet.model_validate(spec['rules'])) if not existing else None
        # Register stable identity before using the ordinary upload/check pipeline.
        from src.services.catalog import now
        if assignment:
            with catalog.database.write() as session:
                session.add(Dataset(id=identity, name=spec['name'], created_at=now(), rule_set_id=assignment.id))
                session.flush()
                catalog.audit(session, identity, 'dataset_created', identity)
        saved = catalog.upload(content, parse_dataset(content, spec['filename'], catalog.settings), identity)
        if saved.check_run.processing_status != 'completed':
            raise RuntimeError(f'Demo validation failed: {identity}')
        output.append({'id': identity, 'created': True, 'rows': saved.metadata.row_count})
    return output


def main() -> None:
    settings = Settings()
    catalog = Catalog(settings, load_rules(settings.rules_path))
    try:
        catalog.initialize()
        print(json.dumps(seed_demo(catalog), indent=2))
    finally:
        catalog.database.close()


if __name__ == '__main__':
    main()
