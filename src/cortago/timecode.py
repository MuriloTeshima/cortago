"""Tempos digitados pelo usuário (1:20:00, 80:00, 4800, 1h20m) e links com o minuto exato."""

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_UNITS = re.compile(r"^(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m(?!s))?(?:(\d+(?:\.\d+)?)s?)?$")


def parse(text: str | None) -> float | None:
    """'1:20:00', '80:00', '4800', '4800.5', '1h20m', '1h20m30s', '90s' → segundos. Vazio → None."""
    if text is None or not text.strip():
        return None
    t = text.strip().lower().replace(",", ".").replace(" ", "")
    if ":" in t:
        parts = t.split(":")
        if len(parts) > 3 or not all(re.fullmatch(r"\d+(?:\.\d+)?", p) for p in parts):
            raise ValueError(f"tempo inválido: {text!r} (use 1:20:00, 80:00 ou 4800)")
        seconds = 0.0
        for p in parts:
            seconds = seconds * 60 + float(p)
        return seconds
    m = _UNITS.fullmatch(t)
    if not m or not any(m.groups()):
        raise ValueError(f"tempo inválido: {text!r} (use 1:20:00, 80:00 ou 4800)")
    h, mnt, s = (float(g) if g else 0.0 for g in m.groups())
    return h * 3600 + mnt * 60 + s


def format(seconds: float | None) -> str:
    """Segundos → '1:20:00' ou '4:05'."""
    if seconds is None:
        return "—"
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def at(url: str | None, seconds: float) -> str | None:
    """Link que abre o vídeo no instante dado (YouTube e Twitch). Outros sites: o link original."""
    if not url:
        return url
    t = max(int(seconds), 0)
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k != "t"]
    if "youtube.com" in host or host == "youtu.be":
        query.append(("t", f"{t}s"))
    elif "twitch.tv" in host:
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        query.append(("t", f"{h}h{m}m{s}s"))
    else:
        return url
    return urlunparse(parsed._replace(query=urlencode(query)))
