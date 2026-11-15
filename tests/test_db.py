from sqlalchemy import create_engine
from sqlmodel.pool import StaticPool

from cortago import db


def test_migrate_adds_missing_columns_with_defaults():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with eng.begin() as conn:
        # Esquema da v0.2.0, antes da música de fundo.
        conn.exec_driver_sql(
            "CREATE TABLE job (id INTEGER PRIMARY KEY AUTOINCREMENT, source VARCHAR NOT NULL, "
            "status VARCHAR(12) NOT NULL, layout VARCHAR NOT NULL, max_clips INTEGER NOT NULL, "
            "min_seconds INTEGER NOT NULL, max_seconds INTEGER NOT NULL, input_tokens INTEGER NOT NULL, "
            "output_tokens INTEGER NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, "
            "error VARCHAR, title VARCHAR, channel VARCHAR, url VARCHAR, duration FLOAT, source_file VARCHAR, "
            "language VARCHAR)"
        )
        conn.exec_driver_sql(
            "INSERT INTO job (source, status, layout, max_clips, min_seconds, max_seconds, input_tokens, "
            "output_tokens, created_at, updated_at) VALUES ('x', 'DONE', 'blur', 5, 20, 60, 0, 0, "
            "'2026-11-14 00:00:00', '2026-11-14 00:00:00')"
        )

    added = db.migrate(eng)

    assert "job.music" in added
    with eng.connect() as conn:
        assert conn.exec_driver_sql("SELECT music FROM job").scalar() == 1
    assert db.migrate(eng) == []  # idempotente
