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
    # Valores padrão fixos: os testes não podem depender do .env de quem roda.
    monkeypatch.setattr(config, "CHANNEL_CONTEXT", "um canal brasileiro de cortes de games no YouTube Shorts")
    monkeypatch.setattr(config, "HIGHLIGHT_COLOR", "#FFE500")
    monkeypatch.setattr(config, "HOOK_BOX_COLOR", "#000000")
    monkeypatch.setattr(config, "MUSIC_GAP_DB", 12.0)
    db.use_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    yield
