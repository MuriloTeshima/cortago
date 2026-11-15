"""Baixa o vídeo de origem com yt-dlp (ou aceita um arquivo local)."""

import json
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel


class SourceInfo(BaseModel):
    id: str
    title: str
    channel: str
    url: str
    duration: float
    path: Path


def _slug(text: str) -> str:
    keep = "".join(c if c.isalnum() else "-" for c in text.lower())
    return "-".join(filter(None, keep.split("-")))[:60] or "video"


def fetch(source: str, jobs_dir: Path) -> SourceInfo:
    local = Path(source).expanduser()
    if local.exists():
        return _from_local(local, jobs_dir)
    return _from_url(source, jobs_dir)


def _from_local(path: Path, jobs_dir: Path) -> SourceInfo:
    job_dir = jobs_dir / _slug(path.stem)
    job_dir.mkdir(parents=True, exist_ok=True)
    target = job_dir / f"source{path.suffix}"
    if not target.exists():
        shutil.copy2(path, target)
    return SourceInfo(
        id=job_dir.name,
        title=path.stem,
        channel="(arquivo local)",
        url="",
        duration=_probe_duration(target),
        path=target,
    )


def _from_url(url: str, jobs_dir: Path) -> SourceInfo:
    meta = json.loads(
        subprocess.run(
            ["yt-dlp", "--dump-single-json", "--no-playlist", url],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    job_dir = jobs_dir / meta["id"]
    job_dir.mkdir(parents=True, exist_ok=True)
    target = job_dir / "source.mp4"

    if not target.exists():
        subprocess.run(
            [
                "yt-dlp",
                "--no-playlist",
                "-f",
                "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b",
                "--merge-output-format",
                "mp4",
                "-o",
                str(target),
                url,
            ],
            check=True,
        )

    return SourceInfo(
        id=meta["id"],
        title=meta.get("title", ""),
        channel=meta.get("channel") or meta.get("uploader") or "",
        url=meta.get("webpage_url", url),
        duration=float(meta.get("duration") or _probe_duration(target)),
        path=target,
    )


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return float(out.strip())
