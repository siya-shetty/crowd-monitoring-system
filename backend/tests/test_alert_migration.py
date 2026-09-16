import importlib.util
import uuid
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from app.db.session import engine


def test_alert_migration_roundtrip():
    path=Path(__file__).resolve().parents[1]/'alembic/versions/20260916_07_add_alert_rules_and_events.py'
    spec=importlib.util.spec_from_file_location('alert_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.down_revision=='20260916_06'
    with engine.connect() as connection:
        transaction=connection.begin()
        try:
            schema='alert_migration_'+uuid.uuid4().hex
            connection.execute(text(f'CREATE SCHEMA {schema}'))
            connection.execute(text(f'SET LOCAL search_path TO {schema}'))
            connection.execute(text('CREATE TABLE videos (id UUID PRIMARY KEY, crowd_analysis JSON)'))
            connection.execute(text('CREATE TABLE monitoring_zones (id UUID PRIMARY KEY)'))
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                indexes=connection.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname=:s"),{'s':schema}).scalars().all()
                assert 'uq_alert_rule_interval' in indexes and 'ix_alert_events_severity' in indexes
                module.downgrade()
                module.upgrade()
                assert connection.execute(text('SELECT count(*) FROM alert_rules')).scalar_one()==0
        finally:transaction.rollback()
