"""Interface web: enviar vídeos, acompanhar o processamento e revisar os cortes."""

import shutil
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import delete, select

from cortago import config, db, pipeline, render, transcribe, worker
from cortago.db import Clip, ClipStatus, Job, RenderStatus

HERE = Path(__file__).parent
MAX_CLIP_SECONDS = 180

STATUS_LABELS = {
    "queued": "Na fila",
    "downloading": "Baixando",
    "transcribing": "Transcrevendo",
    "selecting": "Escolhendo cortes",
    "rendering": "Renderizando",
    "done": "Pronto",
    "error": "Erro",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.engine()
    config.JOBS_DIR.mkdir(parents=True, exist_ok=True)
    worker.recover()
    yield


app = FastAPI(title="CortaGo", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals.update(
    STATUS_LABELS=STATUS_LABELS,
    LAYOUTS=render.LAYOUTS,
    clip_text=pipeline.clip_text,
)


def _fmt_time(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _local(dt: datetime) -> str:
    # SQLite devolve datetime sem fuso; gravamos sempre em UTC.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone().strftime("%d/%m %H:%M")


templates.env.filters["time"] = _fmt_time
templates.env.filters["local"] = _local


# ---------- helpers ----------


def _get_job(job_id: int) -> Job:
    with db.session() as s:
        job = s.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job não encontrado")
    return job


def _get_clip(clip_id: int) -> tuple[Clip, Job]:
    with db.session() as s:
        clip = s.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(404, "Corte não encontrado")
    return clip, _get_job(clip.job_id)


def _clip_transcript(job: Job, clip: Clip) -> str:
    cache = pipeline.job_dir(job) / "transcript.json"
    if not cache.exists():
        return ""
    tr = transcribe.Transcript.model_validate_json(cache.read_text())
    return " ".join(w.text for w in tr.words if w.end > clip.start and w.start < clip.end)


def _clip_card(request: Request, clip: Clip, job: Job) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_clip_card.html",
        {"clip": clip, "job": job, "transcript": _clip_transcript(job, clip)},
    )


def _job_panel(request: Request, job: Job) -> HTMLResponse:
    clips = db.job_clips(job.id)  # type: ignore[arg-type]
    return templates.TemplateResponse(
        request,
        "_job_panel.html",
        {
            "job": job,
            "clips": clips,
            "transcripts": {c.id: _clip_transcript(job, c) for c in clips},
        },
    )


def _jobs() -> list[Job]:
    with db.session() as s:
        return list(s.exec(select(Job).order_by(Job.id.desc())))  # type: ignore[union-attr]


# ---------- páginas ----------


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"jobs": _jobs()})


@app.get("/jobs/list", response_class=HTMLResponse)
def jobs_list(request: Request):
    return templates.TemplateResponse(request, "_jobs_list.html", {"jobs": _jobs()})


@app.post("/jobs")
def create_job(
    source: Annotated[str, Form()],
    max_clips: Annotated[int, Form(ge=1, le=20)] = 5,
    layout: Annotated[str, Form()] = "blur",
    language: Annotated[str, Form()] = "",
    min_seconds: Annotated[int, Form(ge=5, le=170)] = 20,
    max_seconds: Annotated[int, Form(ge=10, le=MAX_CLIP_SECONDS)] = 60,
):
    if not source.strip():
        raise HTTPException(400, "Informe uma URL ou caminho de arquivo")
    try:
        job = pipeline.create_job(
            source,
            layout=layout,
            max_clips=max_clips,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            language=language or None,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    worker.submit_job(job.id)  # type: ignore[arg-type]
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: int):
    job = _get_job(job_id)
    clips = db.job_clips(job_id)
    return templates.TemplateResponse(
        request,
        "job.html",
        {"job": job, "clips": clips, "transcripts": {c.id: _clip_transcript(job, c) for c in clips}},
    )


@app.get("/jobs/{job_id}/panel", response_class=HTMLResponse)
def job_panel(request: Request, job_id: int):
    return _job_panel(request, _get_job(job_id))


@app.post("/jobs/{job_id}/retry", response_class=HTMLResponse)
def job_retry(request: Request, job_id: int):
    worker.submit_job(job_id)
    return _job_panel(request, _get_job(job_id))


@app.post("/jobs/{job_id}/reselect", response_class=HTMLResponse)
def job_reselect(request: Request, job_id: int):
    worker.submit_job(job_id, reselect=True)
    return _job_panel(request, _get_job(job_id))


@app.post("/jobs/{job_id}/delete")
def job_delete(job_id: int):
    job = _get_job(job_id)
    if job.status.running:
        raise HTTPException(409, "Espere o processamento terminar antes de apagar")
    with db.session() as s:
        s.exec(delete(Clip).where(Clip.job_id == job_id))  # type: ignore[arg-type]
        s.exec(delete(Job).where(Job.id == job_id))  # type: ignore[arg-type]
        s.commit()
    shutil.rmtree(pipeline.job_dir(job), ignore_errors=True)
    return Response(headers={"HX-Redirect": "/"})


# ---------- cortes ----------


@app.get("/clips/{clip_id}", response_class=HTMLResponse)
def clip_card(request: Request, clip_id: int):
    clip, job = _get_clip(clip_id)
    return _clip_card(request, clip, job)


@app.post("/clips/{clip_id}", response_class=HTMLResponse)
def clip_update(
    request: Request,
    clip_id: int,
    title: Annotated[str, Form()],
    hook: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    hashtags: Annotated[str, Form()] = "",
    start: Annotated[float, Form(ge=0)] = 0,
    end: Annotated[float, Form(gt=0)] = 0,
):
    clip, job = _get_clip(clip_id)
    if end <= start:
        raise HTTPException(400, "O fim precisa ser depois do início")
    if end - start > MAX_CLIP_SECONDS:
        raise HTTPException(400, f"O corte pode ter no máximo {MAX_CLIP_SECONDS}s")
    if job.duration and end > job.duration + 0.5:
        raise HTTPException(400, "O fim passa da duração do vídeo")

    needs_render = (start, end, hook.strip()) != (clip.start, clip.end, clip.hook)
    clip = db.update_clip(
        clip_id,
        title=title.strip(),
        hook=hook.strip(),
        description=description.strip(),
        hashtags=[t.strip().lstrip("#") for t in hashtags.replace(",", " ").split() if t.strip("# ")],
        start=start,
        end=end,
    )
    if needs_render:
        worker.submit_render(clip_id)
        clip, job = _get_clip(clip_id)
    elif clip.render_status == RenderStatus.DONE:
        pipeline.write_clip_text(job, clip)
    return _clip_card(request, clip, job)


@app.post("/clips/{clip_id}/status", response_class=HTMLResponse)
def clip_set_status(request: Request, clip_id: int, status: Annotated[ClipStatus, Form()]):
    _, job = _get_clip(clip_id)
    clip = db.update_clip(clip_id, status=status)
    if status != ClipStatus.DISCARDED and clip.render_status in (RenderStatus.PENDING, RenderStatus.ERROR):
        worker.submit_render(clip_id)
        clip, job = _get_clip(clip_id)
    return _clip_card(request, clip, job)


@app.post("/clips/{clip_id}/render", response_class=HTMLResponse)
def clip_render(request: Request, clip_id: int):
    worker.submit_render(clip_id)
    clip, job = _get_clip(clip_id)
    return _clip_card(request, clip, job)


@app.get("/media/{job_id}/{clip_id}.mp4")
def clip_media(job_id: int, clip_id: int, download: bool = False):
    clip, job = _get_clip(clip_id)
    if clip.job_id != job_id:
        raise HTTPException(404)
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
