"""Arquivos dos cortes: vídeo renderizado e miniatura."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from cortago import pipeline, render
from cortago.web.common import get_clip, get_job

router = APIRouter()


def _clip_for_job(job_id: int, clip_id: int):
    clip, job = get_clip(clip_id)
    if clip.job_id != job_id:
        raise HTTPException(404)
    return clip, job


@router.get("/media/{job_id}/origem")
def source_media(job_id: int):
    """Vídeo de origem do job, para a prévia da timeline (suporta avanço/retrocesso)."""
    job = get_job(job_id)
    path = pipeline.job_dir(job) / (job.source_file or "")
    if not job.source_file or not path.exists():
        raise HTTPException(404, "Vídeo de origem não encontrado")
    return FileResponse(path, media_type="video/mp4")


@router.get("/media/{job_id}/{clip_id}.mp4")
def clip_media(job_id: int, clip_id: int, download: bool = False):
    clip, job = _clip_for_job(job_id, clip_id)
    path = pipeline.clip_path(job, clip)
    if not path.exists():
        raise HTTPException(404, "Vídeo ainda não renderizado")
    filename = f"cortago_{job.id}_{clip.position:02d}.mp4"
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=filename if download else None,
        content_disposition_type="attachment" if download else "inline",
    )


@router.get("/media/{job_id}/{clip_id}.jpg")
def clip_thumbnail(job_id: int, clip_id: int):
    """Miniatura do corte. Cortes renderizados antes de existir miniatura ganham uma na primeira visita."""
    clip, job = _clip_for_job(job_id, clip_id)
    video, thumb = pipeline.clip_path(job, clip), pipeline.clip_path(job, clip, "jpg")
    if not video.exists():
        raise HTTPException(404, "Vídeo ainda não renderizado")
    if not thumb.exists() or thumb.stat().st_mtime < video.stat().st_mtime:
        render.thumbnail(video, thumb)
    return FileResponse(thumb, media_type="image/jpeg")
