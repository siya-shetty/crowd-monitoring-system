from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from app.core.config import get_settings
def create_database_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, connect_args={"connect_timeout": 2})
engine = create_database_engine()
def database_is_available() -> bool:
    try:
        with engine.connect() as connection: connection.execute(text("SELECT 1"))
    except Exception: return False
    return True
