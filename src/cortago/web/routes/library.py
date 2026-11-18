"""Biblioteca de músicas e sons do gancho (prévias)."""

import mimetypes
import subprocess

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from cortago import config, effects, music
from cortago.web.common import templates

router = APIRouter()


@router.get("/musicas", response_class=HTMLResponse)
def music_library(request: Request):
    tracks = [{"file": t, "name": music.display_name(t), "credit": music.credit(t)} for t in music.tracks()]
    return templates.TemplateResponse(
        request, "musicas.html", {"tracks": tracks, "music_dir": config.MUSIC_DIR}
    )


@router.get("/music/{track}")
def music_file(track: str):
    """Serve uma faixa da biblioteca para prévia no navegador."""
    path = music.path(track)
    if path is None:
        raise HTTPException(404, "Música não encontrada")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@router.get("/sfx/{name}.wav")
def sfx_preview(name: str):
    """Prévia do som do gancho (gerado pelo FFmpeg e guardado em cache)."""
    spec = effects.HOOK_SFX.get(name)
    if not spec:
        raise HTTPException(404, "Som não encontrado")
    cache = config.DATA_DIR / "cache" / f"sfx_{name}.wav"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", spec, str(cache)],
            check=True,
            capture_output=True,
        )
    return FileResponse(cache, media_type="audio/wav")
