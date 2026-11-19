"""Fila de processamento em segundo plano para a interface web.

Uma tarefa por vez: transcrição e render disputam a mesma GPU/encoder do Mac,
então rodar em paralelo só deixaria tudo mais lento.
"""

import logging
from concurrent.futures import Future, ThreadPoolExecutor

from sqlmodel import select

from cortago import cancel, db, pipeline
from cortago.db import Clip, Job, JobStatus, RenderStatus

log = logging.getLogger("cortago.worker")

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cortago-worker")


def _guard(job_id: int, tok: int, fn, *args, **kwargs) -> None:
    if cancel.is_cancelled(job_id, tok):  # pediram para parar enquanto esperava na fila
        pipeline.mark_stopped(job_id)
        return
    try:
        with cancel.scope(job_id, tok):
            fn(*args, **kwargs)
    except cancel.Cancelled:
        log.info("vídeo %s: parado pelo usuário", job_id)
        pipeline.mark_stopped(job_id)
    except Exception:
        log.exception("tarefa falhou: %s%s", fn.__name__, args)


def submit_job(job_id: int, reselect: bool = False) -> Future:
    db.update_job(job_id, status=JobStatus.QUEUED, error=None)
    return _executor.submit(
        _guard, job_id, cancel.token(job_id), pipeline.run_job, job_id, log.info, reselect
    )


def submit_render(clip_id: int) -> Future:
    clip = db.update_clip(clip_id, render_status=RenderStatus.PENDING, render_error=None)
    return _executor.submit(_guard, clip.job_id, cancel.token(clip.job_id), pipeline.render_clip, clip_id)


def stop(job_id: int) -> None:
    """Para tudo deste vídeo: a tarefa em andamento (no próximo ponto de verificação, em geral na hora)
    e as que estão na fila."""
    cancel.request(job_id)
    pipeline.mark_stopped(job_id)


def recover() -> None:
    """Reenfileira o que estava em andamento quando o servidor parou."""
    with db.session() as s:
        jobs = [j.id for j in s.exec(select(Job)) if j.status.running]
        # Cortes interrompidos no meio do render, de jobs que já tinham terminado.
        interrupted = select(Clip).where(Clip.render_status == RenderStatus.RENDERING)
        clips = [c.id for c in s.exec(interrupted) if c.job_id not in jobs]
    for job_id in jobs:
        submit_job(job_id)  # type: ignore[arg-type]
    for clip_id in clips:
        submit_render(clip_id)  # type: ignore[arg-type]
