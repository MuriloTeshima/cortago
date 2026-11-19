"""Vídeos (jobs): criar, listar, acompanhar, reprocessar e apagar."""

import shutil
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlmodel import delete, select

from cortago import db, editing, pipeline, timecode, worker
from cortago.db import Clip, Job
from cortago.web.common import get_job, templates

router = APIRouter()


def _jobs() -> list[Job]:
    with db.session() as s:
        return list(s.exec(select(Job).order_by(Job.id.desc())))  # type: ignore[union-attr]


def _gallery(request: Request, job: Job) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_job_panel.html",
        {"job": job, "clips": db.job_clips(job.id)},  # type: ignore[arg-type]
    )


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"jobs": _jobs()})


@router.get("/jobs/list", response_class=HTMLResponse)
def jobs_list(request: Request):
    return templates.TemplateResponse(request, "_jobs_list.html", {"jobs": _jobs()})


@router.post("/jobs")
def create_job(
    source: Annotated[str, Form()],
    max_clips: Annotated[int, Form(ge=1, le=20)] = 5,
    layout: Annotated[str, Form()] = "blur",
    language: Annotated[str, Form()] = "",
    min_seconds: Annotated[int, Form(ge=5, le=170)] = 20,
    max_seconds: Annotated[int, Form(ge=10, le=editing.MAX_CLIP_SECONDS)] = 60,
    music_enabled: Annotated[bool, Form(alias="music")] = False,  # checkbox: ausente quando desmarcado
    range_start: Annotated[str, Form()] = "",
    range_end: Annotated[str, Form()] = "",
    gameplay_source: Annotated[str, Form()] = "",
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
            music=music_enabled,
            range_start=timecode.parse(range_start),
            range_end=timecode.parse(range_end),
            gameplay_source=gameplay_source or None,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    worker.submit_job(job.id)  # type: ignore[arg-type]
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: int):
    job = get_job(job_id)
    return templates.TemplateResponse(request, "job.html", {"job": job, "clips": db.job_clips(job_id)})


@router.get("/jobs/{job_id}/panel", response_class=HTMLResponse)
def job_panel(request: Request, job_id: int):
    return _gallery(request, get_job(job_id))


@router.post("/jobs/{job_id}/retry", response_class=HTMLResponse)
def job_retry(request: Request, job_id: int):
    worker.submit_job(job_id)
    return _gallery(request, get_job(job_id))


@router.post("/jobs/{job_id}/reselect", response_class=HTMLResponse)
def job_reselect(request: Request, job_id: int):
    worker.submit_job(job_id, reselect=True)
    return _gallery(request, get_job(job_id))


@router.post("/jobs/{job_id}/gameplay", response_class=HTMLResponse)
def job_gameplay(request: Request, job_id: int, gameplay_source: Annotated[str, Form()] = ""):
    """Coloca, troca ou tira (campo vazio) a gameplay de fundo e renderiza os cortes de novo."""
    job = get_job(job_id)
    if job.status.running:
        raise HTTPException(409, "Espere o processamento terminar")
    try:
        pipeline.set_gameplay(job_id, gameplay_source)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    worker.submit_job(job_id)
    return _gallery(request, get_job(job_id))


@router.post("/jobs/{job_id}/delete")
def job_delete(job_id: int):
    job = get_job(job_id)
    if job.status.running:
        raise HTTPException(409, "Espere o processamento terminar antes de apagar")
    with db.session() as s:
        s.exec(delete(Clip).where(Clip.job_id == job_id))  # type: ignore[arg-type]
        s.exec(delete(Job).where(Job.id == job_id))  # type: ignore[arg-type]
        s.commit()
    shutil.rmtree(pipeline.job_dir(job), ignore_errors=True)
    return Response(headers={"HX-Redirect": "/"})
