from sqlalchemy import create_engine, text

def test_sqlalchemy_can_connect_to_a_database() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
