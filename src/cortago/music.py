"""Biblioteca de músicas de fundo (pasta local de faixas livres de direitos)."""

import random
from pathlib import Path

from cortago import config

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac", ".opus"}


def library() -> Path:
    config.MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    return config.MUSIC_DIR


def tracks() -> list[str]:
    """Nomes de arquivo das faixas disponíveis, em ordem alfabética."""
    return sorted(p.name for p in library().iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)


def path(track: str) -> Path | None:
    """Caminho da faixa, ou None se não existir. Recusa nomes que tentam sair da pasta."""
    if not track or Path(track).name != track:
        return None
    p = library() / track
    return p if p.is_file() else None


def pick(seed: int | str) -> str | None:
    """Escolhe uma faixa de forma determinística (o mesmo corte recebe sempre a mesma)."""
    available = tracks()
    return random.Random(seed).choice(available) if available else None


def offset(track_duration: float, clip_duration: float, seed: int | str) -> float:
    """Ponto de início dentro da faixa, pra cortes diferentes não começarem todos na intro."""
    room = track_duration - clip_duration - 5
    return round(random.Random(f"offset-{seed}").uniform(0, room), 1) if room > 10 else 0.0


def credit(track: str) -> str | None:
    p = path(track)
    if p is None:
        return None
    txt = p.with_suffix(".txt")
    if not txt.exists():
        return None
    return txt.read_text(encoding="utf-8-sig").strip() or None  # -sig: ignora o BOM do Bloco de Notas


def display_name(track: str) -> str:
    return Path(track).stem.replace("_", " ")
