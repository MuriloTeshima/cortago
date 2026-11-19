"""Cortes: página de edição (uma por corte), seções do editor e ações rápidas.

Cada seção do editor (texto, corte, áudio, efeitos) salva por conta própria. A resposta traz a seção
atualizada e, fora da área alvo (hx-swap-oob), o player e o painel de postagem, que dependem dela.
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from cortago import db, editing, effects, worker
from cortago.db import Clip, ClipStatus, Job
from cortago.web.common import NO_MUSIC, apply, clip_transcript, edit_or_400, get_clip, templates

router = APIRouter()


def _context(clip: Clip, job: Job, **extra) -> dict:
    prev, nxt = editing.neighbors(clip)
    return {
        "clip": clip,
        "job": job,
        "prev": prev,
        "next": nxt,
        "total": len(db.job_clips(job.id)),  # type: ignore[arg-type]
        "transcript": clip_transcript(job, clip),
        **extra,
    }


def _section(request: Request, name: str, clip: Clip, job: Job, saved: bool = True) -> HTMLResponse:
    """Seção atualizada + player e painel de postagem (out-of-band) para refletir a mudança."""
    return templates.TemplateResponse(
        request, f"editor/_{name}.html", _context(clip, job, oob=True, saved=saved)
    )


# ---------- páginas e parciais ----------


@router.get("/clips/{clip_id}", response_class=HTMLResponse)
def clip_page(request: Request, clip_id: int):
    clip, job = get_clip(clip_id)
    return templates.TemplateResponse(request, "clip.html", _context(clip, job))


@router.get("/clips/{clip_id}/tile", response_class=HTMLResponse)
def clip_tile(request: Request, clip_id: int):
    clip, job = get_clip(clip_id)
    return templates.TemplateResponse(request, "_clip_tile.html", {"clip": clip, "job": job})


@router.get("/clips/{clip_id}/player", response_class=HTMLResponse)
def clip_player(request: Request, clip_id: int):
    clip, job = get_clip(clip_id)
    return templates.TemplateResponse(request, "editor/_player.html", _context(clip, job))


# ---------- seções do editor ----------


@router.post("/clips/{clip_id}/texto", response_class=HTMLResponse)
def save_text(
    request: Request,
    clip_id: int,
    title: Annotated[str, Form()] = "",
    hook: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    hashtags: Annotated[str, Form()] = "",
):
    result = edit_or_400(
        editing.update_text, clip_id, title=title, hook=hook, description=description, hashtags=hashtags
    )
    return _section(request, "texto", *apply(result))


@router.post("/clips/{clip_id}/audio", response_class=HTMLResponse)
def save_audio(
    request: Request,
    clip_id: int,
    music_track: Annotated[str, Form()] = NO_MUSIC,
    music_level: Annotated[int, Form(ge=0, le=editing.MAX_MUSIC_LEVEL)] = 100,
):
    track = "" if music_track == NO_MUSIC else music_track
    result = edit_or_400(editing.update_music, clip_id, track=track, level=music_level)
    return _section(request, "audio", *apply(result))


@router.post("/clips/{clip_id}/audio/nivel", response_class=HTMLResponse)
def nudge_music(request: Request, clip_id: int, delta: Annotated[int, Form(ge=-100, le=100)]):
    """Botões − / + do volume da música."""
    result = edit_or_400(editing.nudge_music_level, clip_id, delta)
    return _section(request, "audio", *apply(result))


@router.post("/clips/{clip_id}/efeitos", response_class=HTMLResponse)
def save_effects(
    request: Request,
    clip_id: int,
    jump_cuts: Annotated[bool, Form()] = False,  # checkbox desmarcado não é enviado
    intro_zoom: Annotated[str, Form()] = "none",
    hook_anim: Annotated[bool, Form()] = False,
    hook_sfx: Annotated[str, Form()] = "none",
    progress_bar: Annotated[bool, Form()] = False,
    gameplay_mode: Annotated[str | None, Form()] = None,  # só vem em vídeos com gameplay de fundo
    facecam_layout: Annotated[str | None, Form()] = None,  # só vem em vídeos com webcam marcada
):
    try:
        fx = effects.Effects(jump_cuts, intro_zoom, hook_anim, hook_sfx, progress_bar)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    result = edit_or_400(editing.update_effects, clip_id, fx)
    if gameplay_mode is not None:
        gp = edit_or_400(editing.update_gameplay_mode, clip_id, gameplay_mode)
        result = editing.EditResult(gp.clip, result.rerender or gp.rerender)
    if facecam_layout is not None:
        fc = edit_or_400(editing.update_facecam_layout, clip_id, facecam_layout)
        result = editing.EditResult(fc.clip, result.rerender or fc.rerender)
    return _section(request, "efeitos", *apply(result))


# ---------- ações do player ----------


@router.post("/clips/{clip_id}/status", response_class=HTMLResponse)
def set_status(request: Request, clip_id: int, status: Annotated[ClipStatus, Form()]):
    clip, job = apply(edit_or_400(editing.set_status, clip_id, status))
    return templates.TemplateResponse(request, "editor/_player.html", _context(clip, job))


@router.post("/clips/{clip_id}/parar", response_class=HTMLResponse)
def stop_render(request: Request, clip_id: int):
    """Para a renderização deste corte (e o que estiver na fila para o mesmo vídeo)."""
    clip, job = get_clip(clip_id)
    worker.stop(job.id)  # type: ignore[arg-type]
    clip, job = get_clip(clip_id)
    return templates.TemplateResponse(request, "editor/_player.html", _context(clip, job))


@router.post("/clips/{clip_id}/render", response_class=HTMLResponse)
def rerender(request: Request, clip_id: int):
    get_clip(clip_id)
    worker.submit_render(clip_id)
    clip, job = get_clip(clip_id)
    return templates.TemplateResponse(request, "editor/_player.html", _context(clip, job))
