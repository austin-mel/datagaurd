from alembic import context
from sqlalchemy.engine import Connection

from src.database import Database
from src.models import Base
from src.settings import Settings


def migrate(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    migrate(connection)
else:
    database = Database(Settings().storage_dir)
    database.directory.mkdir(parents=True, exist_ok=True)
    with database.engine.begin() as connection:
        migrate(connection)
    database.close()

