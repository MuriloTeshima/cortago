"""Baixa o vídeo de origem com yt-dlp (ou aceita um arquivo local)."""

import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel


class SourceInfo(BaseModel):
    title: str
    channel: str
    url: str
    duration: float
    path: Path


def slug(text: str) -> str:
    keep = "".join(c if c.isalnum() else "-" for c in text.lower())
    return "-".join(filter(None, keep.split("-")))[:60] or "video"


def is_local(source: str) -> bool:
    return Path(source).expanduser().exists()


def fetch(source: str, job_dir: Path) -> SourceInfo:
    job_dir.mkdir(parents=True, exist_ok=True)
    if is_local(source):
        return _from_local(Path(source).expanduser(), job_dir)
    return _from_url(source, job_dir)


def _from_local(path: Path, job_dir: Path) -> SourceInfo:
    target = job_dir / f"source{path.suffix.lower()}"
    if not target.exists():
        shutil.copy2(path, target)
    return SourceInfo(
        title=path.stem,
        channel="(arquivo local)",
        url="",
        duration=probe_duration(target),
        path=target,
    )


def _from_url(url: str, job_dir: Path) -> SourceInfo:
    import yt_dlp  # biblioteca Python: funciona igual em qualquer sistema, sem depender do PATH

    target = job_dir / "source.mp4"
    options = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(target),
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        meta = ydl.extract_info(url, download=not target.exists())

    return SourceInfo(
        title=meta.get("title", ""),
        channel=meta.get("channel") or meta.get("uploader") or "",
        url=meta.get("webpage_url", url),
        duration=float(meta.get("duration") or probe_duration(target)),
        path=target,
    )


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    return float(out.strip())
