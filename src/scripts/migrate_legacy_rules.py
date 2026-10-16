"""Append compatible rule revisions/checks without rewriting historical evidence."""
import json
from copy import deepcopy
from typing import Any

from sqlalchemy import select

from src.models import CheckRun, Dataset, DatasetVersion, RuleSetRecord
from src.rules import RuleSet, load_rules
from src.services.catalog import Catalog
from src.settings import Settings


def upgrade(configuration: dict[str, Any], reference_date: str) -> RuleSet:
    document = deepcopy(configuration)
    originals = {rule['id']: rule for rule in document['rules']}
    for rule in document['rules']:
        if rule['kind'] == 'date':
            # Date parsing is equivalent to a valid ISO calendar date <= year 9999.
            rule.update(kind='on_or_before_date', date='9999-12-31')
        elif rule['kind'] == 'not_future':
            prerequisite = originals[rule.pop('prerequisite')]
            latest = rule.pop('latest', 'today')
            rule.update(kind='on_or_before_date', date=reference_date if latest == 'today' else latest,
                        formats=prerequisite.get('formats', ['%Y-%m-%d']))
            rule['explanation'] += f' Migrated with the recorded cutoff {rule["date"]}.'
    document['name'] += ' (compatible revision)'
    return RuleSet.model_validate(document)


def migrate(catalog: Catalog) -> list[str]:
    migrated: list[str] = []
    with catalog.database.read() as session:
        datasets = list(session.scalars(select(Dataset)))
    for dataset in datasets:
        with catalog.database.read() as session:
            assignment = session.get(RuleSetRecord, dataset.rule_set_id)
            if assignment is None:
                continue
            configuration = json.loads(assignment.configuration_json)
            if not any(rule['kind'] in {'date', 'not_future'} for rule in configuration['rules']):
                continue
            version = session.scalar(select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)
                                     .order_by(DatasetVersion.number.desc()))
            if version is None:
                continue
            run = session.scalar(select(CheckRun).where(CheckRun.version_id == version.id)
                                 .order_by(CheckRun.created_at.desc()))
            if run is None:
                raise RuntimeError('Legacy rules require a recorded reference date before migration.')
            rules = upgrade(configuration, run.reference_date)
        saved = catalog.create_rule_set(rules)
        catalog.assign_rules(dataset.id, saved.id)
        result = catalog.check(version.id)
        if result.processing_status != 'completed':
            raise RuntimeError(f'Revalidation failed for {dataset.id}: {result.error_code}')
        migrated.append(dataset.id)
    return migrated


def main() -> None:
    settings = Settings()
    catalog = Catalog(settings, load_rules(settings.rules_path))
    try:
        catalog.initialize()
        print(json.dumps({'migrated': migrate(catalog)}))
    finally:
        catalog.database.close()


if __name__ == '__main__':
    main()
