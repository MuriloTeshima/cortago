"""Timeline do editor: dados (trechos, palavras), imagens (onda e miniaturas), salvar e restaurar."""

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse

from cortago import editing, pipeline, render, timeline, transcribe
from cortago.db import Clip, Job
from cortago.web.common import apply, edit_or_400, get_clip

router = APIRouter()


def _source(job: Job):
    path = pipeline.job_dir(job) / (job.source_file or "")
    if not job.source_file or not path.exists():
        raise HTTPException(404, "Vídeo de origem não encontrado")
    return path


def _transcript(job: Job) -> transcribe.Transcript:
    cache = pipeline.job_dir(job) / "transcript.json"
    if not cache.exists():
        raise HTTPException(404, "Transcrição não encontrada")
    return transcribe.Transcript.model_validate_json(cache.read_text(encoding="utf-8"))


def _window(job: Job, clip: Clip) -> tuple[float, float]:
    return timeline.display_window(clip.start, clip.end, job.file_end())


def _asset(job: Job, clip: Clip, kind: str, ext: str):
    """Imagem da timeline em cache, uma por janela (muda quando o corte é estendido)."""
    lo, hi = _window(job, clip)
    path = pipeline.job_dir(job) / "clips" / f"{clip.file_stem}.{kind}-{lo:.1f}-{hi:.1f}.{ext}"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        generate = render.waveform if kind == "onda" else render.filmstrip
        generate(_source(job), lo, hi, path)
    return path


@router.get("/clips/{clip_id}/timeline.json")
def timeline_data(clip_id: int):
    clip, job = get_clip(clip_id)
    source = _source(job)
    tr = _transcript(job)
    lo, hi = _window(job, clip)
    fixes = timeline.word_fixes(clip.edit)
    manual = timeline.manual_segments(clip.edit)

    automatic = pipeline.effective_segments(source, clip.model_copy(update={"edit": None}), tr.words, None)
    automatic = automatic or [(clip.start, clip.end)]

    return {
        "clip_id": clip.id,
        "offset": job.source_offset,  # soma para mostrar no tempo do vídeo original
        "window": [lo, hi],
        "segments": [list(s) for s in (manual or automatic)],
        "auto_segments": [list(s) for s in automatic],
        "manual": manual is not None,
        "words": [
            {
                "key": timeline.word_key(w),
                "text": fixes.get(timeline.word_key(w), w.text),
                "original": w.text,
                "start": w.start,
                "end": w.end,
            }
            for w in tr.words
            if w.end > lo and w.start < hi
        ],
        "max_seconds": editing.MAX_CLIP_SECONDS,
        "source": f"/media/{job.id}/origem",
        "waveform": f"/clips/{clip.id}/timeline/onda.png?janela={lo:.1f}-{hi:.1f}",
        "filmstrip": f"/clips/{clip.id}/timeline/miniaturas.jpg?janela={lo:.1f}-{hi:.1f}",
    }


@router.get("/clips/{clip_id}/timeline/onda.png")
def timeline_waveform(clip_id: int):
    clip, job = get_clip(clip_id)
    return FileResponse(_asset(job, clip, "onda", "png"), media_type="image/png")


@router.get("/clips/{clip_id}/timeline/miniaturas.jpg")
def timeline_filmstrip(clip_id: int):
    clip, job = get_clip(clip_id)
    return FileResponse(_asset(job, clip, "miniaturas", "jpg"), media_type="image/jpeg")


@router.post("/clips/{clip_id}/timeline")
def timeline_save(clip_id: int, payload: dict = Body(...)):  # noqa: B008
    segments = payload.get("segments") or []
    if not isinstance(segments, list) or not all(
        isinstance(s, list | tuple) and len(s) == 2 for s in segments
    ):
        raise HTTPException(400, "Trechos inválidos")
    words = payload.get("words") or {}
    if not isinstance(words, dict):
        raise HTTPException(400, "Correções de legenda inválidas")
    result = edit_or_400(
        editing.update_timeline, clip_id, segments=[tuple(s) for s in segments], word_fixes=words
    )
    clip, _ = apply(result)
    return {"saved": True, "rerender": result.rerender, "render_status": clip.render_status}


@router.post("/clips/{clip_id}/timeline/restaurar")
def timeline_reset(clip_id: int):
    result = edit_or_400(editing.reset_timeline, clip_id)
    clip, _ = apply(result)
    return {"saved": True, "rerender": result.rerender, "render_status": clip.render_status}
