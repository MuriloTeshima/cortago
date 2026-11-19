"""Peças compartilhadas pelas rotas: templates, filtros e acesso a vídeos e cortes."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from fastapi.templating import Jinja2Templates

from cortago import (
    config,
    db,
    editing,
    effects,
    facecam,
    gameplay,
    music,
    pipeline,
    post_info,
    render,
    timecode,
    transcribe,
    worker,
)
from cortago.db import Clip, Job

HERE = Path(__file__).parent

MUSIC_LEVEL_STEP = 25  # passo dos botões rápidos − / +
# Valor do <select> para "sem música". Não pode ser "": o FastAPI trata campo vazio como ausente.
NO_MUSIC = "__none__"

STATUS_LABELS = {
    "queued": "Na fila",
    "downloading": "Baixando",
    "transcribing": "Transcrevendo",
    "selecting": "Escolhendo cortes",
    "rendering": "Renderizando",
    "done": "Pronto",
    "error": "Erro",
    "cancelled": "Parado",
}

ZOOM_LABELS = {"none": "Sem zoom", "suave": "Suave", "forte": "Forte"}
SFX_LABELS = {"none": "Sem som", "whoosh": "Whoosh", "pop": "Pop", "impact": "Impact"}


def _local(dt: datetime) -> str:
    # SQLite devolve datetime sem fuso; gravamos sempre em UTC.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone().strftime("%d/%m %H:%M")


def effects_summary(clip: Clip) -> list[str]:
    items = []
    if clip.jump_cuts:
        items.append("sem silêncios")
    if clip.intro_zoom != "none":
        items.append(f"zoom {clip.intro_zoom}")
    if clip.hook_anim:
        items.append("gancho animado")
    if clip.hook_sfx != "none":
        items.append(f"som {clip.hook_sfx}")
    if clip.progress_bar:
        items.append("barra")
    if clip.facecam_layout == "dividida":
        items.append("webcam em cima")
    elif clip.facecam_layout == "camera":
        items.append("só a webcam")
    if clip.gameplay_mode == "alternar":
        items.append("gameplay alternando")
    elif clip.gameplay_mode == "dividida":
        items.append("tela dividida")
    return items


def static_url(name: str) -> str:
    """URL de um arquivo de /static com a data de modificação, para o navegador não usar versão velha do cache."""
    path = HERE / "static" / name
    version = int(path.stat().st_mtime) if path.exists() else 0
    return f"/static/{name}?v={version}"


templates = Jinja2Templates(directory=HERE / "templates")
templates.env.filters["time"] = timecode.format
templates.env.filters["local"] = _local
templates.env.globals.update(
    static=static_url,
    STOPPED=pipeline.STOPPED,
    GAMEPLAY_MODES=gameplay.MODE_LABELS,
    FACECAM_LAYOUTS=facecam.LAYOUT_LABELS,
    STATUS_LABELS=STATUS_LABELS,
    LAYOUTS=render.LAYOUTS,
    post_info=post_info.build,
    TITLE_LIMIT=post_info.TITLE_LIMIT,
    DESCRIPTION_LIMIT=post_info.DESCRIPTION_LIMIT,
    TAGS_LIMIT=post_info.TAGS_LIMIT,
    music_tracks=music.tracks,
    music_name=music.display_name,
    MUSIC_DIR=config.MUSIC_DIR,
    NO_MUSIC=NO_MUSIC,
    INTRO_ZOOMS=list(effects.INTRO_ZOOMS),
    HOOK_SFX=list(effects.HOOK_SFX),
    ZOOM_LABELS=ZOOM_LABELS,
    SFX_LABELS=SFX_LABELS,
    MAX_MUSIC_LEVEL=editing.MAX_MUSIC_LEVEL,
    MUSIC_LEVEL_STEP=MUSIC_LEVEL_STEP,
    effects_summary=effects_summary,
)


def get_job(job_id: int) -> Job:
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Vídeo não encontrado")
    return job


def get_clip(clip_id: int) -> tuple[Clip, Job]:
    with db.session() as s:
        clip = s.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(404, "Corte não encontrado")
    return clip, get_job(clip.job_id)


def clip_transcript(job: Job, clip: Clip) -> str:
    cache = pipeline.job_dir(job) / "transcript.json"
    if not cache.exists():
        return ""
    tr = transcribe.Transcript.model_validate_json(cache.read_text(encoding="utf-8"))
    return " ".join(w.text for w in tr.words if w.end > clip.start and w.start < clip.end)


def apply(result: editing.EditResult) -> tuple[Clip, Job]:
    """Enfileira o render quando a edição pede e devolve o corte atualizado."""
    if result.rerender:
        worker.submit_render(result.clip.id)  # type: ignore[arg-type]
    return get_clip(result.clip.id)  # type: ignore[arg-type]


def edit_or_400(fn, *args, **kwargs) -> editing.EditResult:
    try:
        return fn(*args, **kwargs)
    except editing.EditError as exc:
        raise HTTPException(400, str(exc)) from exc
