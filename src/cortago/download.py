"""Baixa o vídeo de origem com yt-dlp (ou aceita um arquivo local)."""

import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel


class SourceInfo(BaseModel):
    title: str
    channel: str
    url: str
    duration: float  # duração do vídeo original inteiro
    path: Path
    offset: float = 0.0  # segundo do vídeo original em que o arquivo baixado começa


def slug(text: str) -> str:
    keep = "".join(c if c.isalnum() else "-" for c in text.lower())
    return "-".join(filter(None, keep.split("-")))[:60] or "video"


def is_local(source: str) -> bool:
    return Path(source).expanduser().exists()


def fetch(source: str, job_dir: Path, section: tuple[float, float | None] | None = None) -> SourceInfo:
    """Baixa o vídeo. Com `section` (início, fim em segundos), links baixam só esse trecho quando o site permite."""
    job_dir.mkdir(parents=True, exist_ok=True)
    if is_local(source):
        return _from_local(Path(source).expanduser(), job_dir)
    return _from_url(source, job_dir, section)


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


def _from_url(url: str, job_dir: Path, section: tuple[float, float | None] | None = None) -> SourceInfo:
    if section and (section[0] > 0 or section[1] is not None):
        try:
            return _download(url, job_dir, section)
        except Exception:
            # Nem todo site aceita baixar só um trecho: baixa inteiro e o trecho é aplicado na transcrição.
            for leftover in job_dir.glob("source.*"):
                leftover.unlink()
    return _download(url, job_dir, None)


def _download(url: str, job_dir: Path, section: tuple[float, float | None] | None) -> SourceInfo:
    import yt_dlp  # biblioteca Python: funciona igual em qualquer sistema, sem depender do PATH
    from yt_dlp.utils import download_range_func

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
    offset = 0.0
    if section:
        start, end = section
        options["download_ranges"] = download_range_func(
            None, [(start, end if end is not None else float("inf"))]
        )
        offset = start
    with yt_dlp.YoutubeDL(options) as ydl:
        meta = ydl.extract_info(url, download=not target.exists())
    if not target.exists():
        raise RuntimeError("o download não gerou o arquivo de vídeo")

    return SourceInfo(
        title=meta.get("title", ""),
        channel=meta.get("channel") or meta.get("uploader") or "",
        url=meta.get("webpage_url", url),
        duration=float(meta.get("duration") or probe_duration(target)),
        path=target,
        offset=offset,
    )


# Da gameplay basta um pedaço: pula a abertura e pega até 10 min (cada corte usa um ponto diferente dele).
# Download de trecho passa pelo FFmpeg e anda perto do tempo real (~0,5 MB/s em 1080p): mais que isso só atrasa.
GAMEPLAY_SKIP = 30.0
GAMEPLAY_MAX_SECONDS = 600.0


def gameplay_name(source: str) -> str:
    import hashlib

    return hashlib.sha1(source.strip().encode("utf-8")).hexdigest()[:16]


def fetch_gameplay(source: str, folder: Path) -> Path:
    """Arquivo da gameplay de fundo. Arquivos locais são usados no lugar; links são baixados (só vídeo) uma vez."""
    if is_local(source):
        return Path(source).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    name = gameplay_name(source)
    done = [p for p in folder.glob(f"{name}.*") if not p.name.endswith((".part", ".ytdl"))]
    if done:
        return done[0]

    import yt_dlp
    from yt_dlp.utils import download_range_func

    def options(section: bool) -> dict:
        opts = {
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            # Só a imagem: a voz vem sempre do vídeo principal.
            "format": "bv*[height<=1080][ext=mp4]/bv*[height<=1080]/b[height<=1080]/b",
            "outtmpl": str(folder / f"{name}.%(ext)s"),
        }
        if section:
            opts["download_ranges"] = download_range_func(
                None, [(GAMEPLAY_SKIP, GAMEPLAY_SKIP + GAMEPLAY_MAX_SECONDS)]
            )
        return opts

    try:
        with yt_dlp.YoutubeDL(options(section=True)) as ydl:
            ydl.extract_info(source, download=True)
    except Exception:
        for leftover in folder.glob(f"{name}.*"):
            leftover.unlink()
        with yt_dlp.YoutubeDL(options(section=False)) as ydl:  # site sem download de trecho
            ydl.extract_info(source, download=True)
    done = [p for p in folder.glob(f"{name}.*") if not p.name.endswith((".part", ".ytdl"))]
    if not done:
        raise RuntimeError("o download da gameplay não gerou o arquivo de vídeo")
    return done[0]


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
