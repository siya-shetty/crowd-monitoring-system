import importlib.util
import uuid
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from app.db.session import engine


def test_operations_migration_roundtrip_constraints_and_set_null():
    path=Path(__file__).resolve().parents[1]/'alembic/versions/20260926_09_add_events_incidents.py'
    spec=importlib.util.spec_from_file_location('operations_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.down_revision=='20260916_08'
    with engine.connect() as connection:
        transaction=connection.begin()
        try:
            schema='operations_migration_'+uuid.uuid4().hex
            connection.execute(text(f'CREATE SCHEMA {schema}'))
            connection.execute(text(f'SET LOCAL search_path TO {schema}'))
            for table in ['users','cameras','videos','live_sessions','alert_events','live_alert_events']:
                connection.execute(text(f'CREATE TABLE {table} (id UUID PRIMARY KEY)'))
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                fks=inspect(connection).get_foreign_keys('incidents',schema=schema)
                assert len(fks)==7
                assert all(fk['options']['ondelete']==('CASCADE' if fk['referred_table']=='users' else 'SET NULL') for fk in fks)
                assert len(inspect(connection).get_check_constraints('incidents',schema=schema))==4
                module.downgrade();module.upgrade()
                assert connection.execute(text('SELECT count(*) FROM incidents')).scalar_one()==0
        finally:transaction.rollback()
