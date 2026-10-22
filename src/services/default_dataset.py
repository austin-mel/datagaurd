"""Populate the connected demo workspace from the bundled facilities CSV."""
from sqlalchemy import select

from src.models import Dataset, DatasetVersion
from src.rules import load_rules
from src.services.catalog import Catalog, now
from src.services.tabular import parse_dataset
from src.settings import PROJECT_ROOT

# Reuse the identity of the original hosted example upload.
DEFAULT_DATASET_ID = "660475ba-0518-41d6-a935-6ed07964eca6"


def seed_default_dataset(catalog: Catalog) -> None:
    # SQLite's write lock makes identity, rules and version creation atomic,
    # including when multiple application processes start together.
    with catalog.database.write() as session:
        dataset = session.get(Dataset, DEFAULT_DATASET_ID)
        version = session.scalar(select(DatasetVersion).where(
            DatasetVersion.dataset_id == DEFAULT_DATASET_ID
        ).order_by(DatasetVersion.number.desc()).limit(1))
        if version is None:
            source = PROJECT_ROOT / "src" / "data" / "facilities_dirty.csv"
            content = source.read_bytes()
            parsed = parse_dataset(content, source.name, catalog.settings)
            if dataset is None:
                assignment = catalog._register_rules(
                    session, load_rules(PROJECT_ROOT / "config" / "facilities.yaml"), reuse=True
                )
                dataset = Dataset(id=DEFAULT_DATASET_ID, name=source.name,
                                  created_at=now(), rule_set_id=assignment.id)
                session.add(dataset)
                session.flush()
                catalog.audit(session, dataset.id, "dataset_created", dataset.id)
            version = catalog.save_version(session, dataset.id, content, parsed, None)
            catalog.audit(session, dataset.id, "version_uploaded", version.id,
                          f"{catalog.settings.actor} · {source.name} · v1")
        run = catalog._latest_run(session, version.id)
        if run is not None and run.processing_status == "completed":
            return  # Preserve existing versions, edits, rules and review decisions.
        if run is None or run.processing_status == "failed":
            run = catalog.start_check(session, version)
        run_id = run.id
    # Resume interrupted initial checks or retry failures without adding a version.
    if catalog.process_check(run_id).processing_status != "completed":
        raise RuntimeError("Default facilities dataset validation failed")
