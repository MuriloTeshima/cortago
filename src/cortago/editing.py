"""Regras de edição de um corte, independentes da interface.

Cada função valida, grava e diz se o vídeo precisa ser renderizado de novo. Quem chama (rotas web, CLI,
futura timeline) decide como enfileirar o render. Erros de validação viram `EditError`, com mensagem
pronta para o usuário.
"""

from dataclasses import dataclass

from cortago import db, effects, music, pipeline, timeline
from cortago.db import Clip, ClipStatus, Job, RenderStatus

MAX_CLIP_SECONDS = 180
MAX_MUSIC_LEVEL = 150  # % do volume automático


class EditError(ValueError):
    """Edição inválida; a mensagem vai direto para o usuário."""


@dataclass(frozen=True)
class EditResult:
    clip: Clip
    rerender: bool


def _load(clip_id: int) -> tuple[Clip, Job]:
    with db.session() as s:
        clip = s.get(Clip, clip_id)
        if clip is None:
            raise EditError("Corte não encontrado")
        job = s.get(Job, clip.job_id)
    assert job is not None
    return clip, job


def _refresh_text(job: Job, clip: Clip) -> None:
    """Sem novo render, o .txt ao lado do vídeo ainda precisa refletir título/descrição novos."""
    if clip.render_status == RenderStatus.DONE:
        pipeline.write_clip_text(job, clip)


def parse_hashtags(text: str) -> list[str]:
    return [t.strip().lstrip("#") for t in text.replace(",", " ").split() if t.strip("# ")]


def update_text(clip_id: int, *, title: str, hook: str, description: str, hashtags: str) -> EditResult:
    """Título, descrição e hashtags só mudam o texto de postagem; o gancho aparece no vídeo."""
    clip, job = _load(clip_id)
    title = title.strip()
    if not title:
        raise EditError("O título não pode ficar vazio")
    hook = hook.strip()
    rerender = hook != clip.hook
    clip = db.update_clip(
        clip_id, title=title, hook=hook, description=description.strip(), hashtags=parse_hashtags(hashtags)
    )
    if not rerender:
        _refresh_text(job, clip)
    return EditResult(clip, rerender)


def update_cut(clip_id: int, *, start: float, end: float) -> EditResult:
    """Início e fim no **tempo do vídeo original** (como a interface mostra)."""
    clip, job = _load(clip_id)
    if end <= start:
        raise EditError("O fim precisa ser depois do início")
    if end - start > MAX_CLIP_SECONDS:
        raise EditError(f"O corte pode ter no máximo {MAX_CLIP_SECONDS}s")
    if start < job.source_offset:
        raise EditError("O início fica antes do trecho baixado")
    # O corte é guardado no tempo do arquivo baixado.
    start, end = start - job.source_offset, end - job.source_offset
    file_end = job.file_end()
    if file_end and end > file_end + 0.5:
        raise EditError("O fim passa do fim do vídeo (ou do trecho escolhido)")
    rerender = (start, end) != (clip.start, clip.end)
    return EditResult(db.update_clip(clip_id, start=start, end=end), rerender)


def update_music(clip_id: int, *, track: str | None, level: int | None = None) -> EditResult:
    """`track`: nome do arquivo, "" para sem música, None para não mexer. `level`: % do volume automático."""
    clip, job = _load(clip_id)
    if track is None:
        track = clip.music_track
    elif track and track not in music.tracks():
        raise EditError("Essa música não está na biblioteca")
    if level is None:
        level = clip.music_level
    elif not 0 <= level <= MAX_MUSIC_LEVEL:
        raise EditError(f"O volume da música vai de 0 a {MAX_MUSIC_LEVEL}%")
    rerender = (track or "", level) != (clip.music_track or "", clip.music_level)
    return EditResult(db.update_clip(clip_id, music_track=track, music_level=level), rerender)


def nudge_music_level(clip_id: int, delta: int) -> EditResult:
    """Botões − / +: soma `delta` ao volume, dentro dos limites."""
    clip, _ = _load(clip_id)
    if not clip.music_track:
        raise EditError("Este corte não tem música")
    level = min(max(clip.music_level + delta, 0), MAX_MUSIC_LEVEL)
    return update_music(clip_id, track=None, level=level)


def update_effects(clip_id: int, fx: effects.Effects) -> EditResult:
    clip, _ = _load(clip_id)
    rerender = fx != effects.Effects.from_clip(clip)
    clip = db.update_clip(
        clip_id,
        jump_cuts=fx.jump_cuts,
        intro_zoom=fx.intro_zoom,
        hook_anim=fx.hook_anim,
        hook_sfx=fx.hook_sfx,
        progress_bar=fx.progress_bar,
    )
    return EditResult(clip, rerender)


def update_timeline(
    clip_id: int, *, segments: list[tuple[float, float]], word_fixes: dict[str, str] | None = None
) -> EditResult:
    """Salva os trechos montados na timeline (em segundos do arquivo) e as correções de legenda.

    Os trechos passam a definir o corte: início e fim viram as bordas do primeiro e do último.
    """
    clip, job = _load(clip_id)
    try:
        ordered = timeline.validate_segments(segments, job.file_end())
        fixes = timeline.validate_word_fixes(word_fixes or {})
    except ValueError as exc:
        raise EditError(str(exc)) from exc
    total = sum(b - a for a, b in ordered)
    if total > MAX_CLIP_SECONDS:
        raise EditError(f"O corte pode ter no máximo {MAX_CLIP_SECONDS}s")
    edit = {"segments": [list(s) for s in ordered], "words": fixes}
    rerender = edit != (clip.edit or {}) or (ordered[0][0], ordered[-1][1]) != (clip.start, clip.end)
    clip = db.update_clip(clip_id, edit=edit, start=ordered[0][0], end=ordered[-1][1])
    return EditResult(clip, rerender)


def reset_timeline(clip_id: int) -> EditResult:
    """Descarta os ajustes manuais da timeline e volta ao automático (corte do Claude + efeitos)."""
    clip, _ = _load(clip_id)
    if not clip.edit:
        return EditResult(clip, False)
    return EditResult(db.update_clip(clip_id, edit=None), True)


def set_status(clip_id: int, status: ClipStatus) -> EditResult:
    """Aprovar/descartar/restaurar. Um corte que voltou a valer e não tem vídeo pronto é renderizado."""
    _load(clip_id)
    clip = db.update_clip(clip_id, status=status)
    rerender = status != ClipStatus.DISCARDED and clip.render_status in (
        RenderStatus.PENDING,
        RenderStatus.ERROR,
    )
    return EditResult(clip, rerender)


def neighbors(clip: Clip) -> tuple[Clip | None, Clip | None]:
    """Corte anterior e seguinte do mesmo vídeo, para navegar no editor."""
    clips = db.job_clips(clip.job_id)
    ids = [c.id for c in clips]
    i = ids.index(clip.id)
    return (clips[i - 1] if i > 0 else None, clips[i + 1] if i + 1 < len(clips) else None)
