import pytest
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from cortago import config, db


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Cada teste usa um banco em memória e uma pasta de dados própria."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(config, "MUSIC_DIR", tmp_path / "music")
    db.use_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    yield
