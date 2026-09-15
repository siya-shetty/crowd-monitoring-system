import sys
from pathlib import Path
from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.base import Base
config = context.config
target_metadata = Base.metadata
def run_migrations_offline() -> None: context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True); context.run_migrations()
def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection: context.configure(connection=connection, target_metadata=target_metadata); context.run_migrations()
if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()
