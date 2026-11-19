import math
import os
import sys
import threading
import time

import pytest

from cortago import cancel, db, pipeline, worker
from cortago.db import Clip, JobStatus, RenderStatus

SLEEP = [sys.executable, "-c", "import time; time.sleep(30)"]


def run_in_scope(job_id, fn):
    """Roda `fn` numa thread, como o worker faz; devolve (thread, resultado)."""
    out = {}

    def target():
        with cancel.scope(job_id, cancel.token(job_id)):
            try:
                out["value"] = fn()
            except BaseException as exc:  # noqa: BLE001
                out["error"] = exc

    t = threading.Thread(target=target)
    t.start()
    return t, out


def test_request_invalidates_existing_tokens_only():
    tok = cancel.token(901)
    assert not cancel.is_cancelled(901, tok)
    cancel.request(901)
    assert cancel.is_cancelled(901, tok)
    assert not cancel.is_cancelled(901, cancel.token(901))  # o que vier depois vale
    assert not cancel.is_cancelled(902, cancel.token(902))  # outros vídeos não são afetados


def test_check_outside_worker_does_nothing():
    cancel.request(903)
    cancel.check()  # sem escopo (CLI): nada a fazer


def test_check_inside_scope():
    tok = cancel.token(904)
    with cancel.scope(904, tok):
        cancel.check()
        cancel.request(904)
        with pytest.raises(cancel.Cancelled):
            cancel.check()
    assert cancel.current() is None


def test_run_returns_output_and_raises_on_error():
    # PYTHONUTF8: no Windows o Python filho escreveria em cp1252 (o FFmpeg não tem esse problema).
    env = {**os.environ, "PYTHONUTF8": "1"}
    r = cancel.run([sys.executable, "-c", "print('olá')"], text=True, check=True, env=env)
    assert r.stdout.strip() == "olá" and r.returncode == 0
    with pytest.raises(Exception) as info:
        cancel.run([sys.executable, "-c", "import sys; sys.exit(3)"], check=True)
    assert info.value.returncode == 3


def test_run_kills_process_when_stopped():
    t, out = run_in_scope(905, lambda: cancel.run(SLEEP))
    time.sleep(0.5)
    started = time.monotonic()
    cancel.request(905)
    t.join(10)
    assert not t.is_alive() and time.monotonic() - started < 5
    assert isinstance(out.get("error"), cancel.Cancelled)


def test_call_runs_in_separate_process_and_returns():
    assert cancel.call(math.sqrt, 16) == 4  # sem escopo: direto
    t, out = run_in_scope(906, lambda: cancel.call(math.sqrt, 81))
    t.join(60)
    assert out == {"value": 9.0}


def test_call_propagates_errors():
    t, out = run_in_scope(907, lambda: cancel.call(int, "não é número"))
    t.join(60)
    assert isinstance(out.get("error"), ValueError)


def test_call_stops_the_process():
    t, out = run_in_scope(908, lambda: cancel.call(time.sleep, 60))
    time.sleep(1.5)  # deixa o processo subir
    started = time.monotonic()
    cancel.request(908)
    t.join(15)
    assert not t.is_alive() and time.monotonic() - started < 10
    assert isinstance(out.get("error"), cancel.Cancelled)


# ---------- estado depois de parar ----------


@pytest.fixture
def job_with_clips():
    job = pipeline.create_job("https://x")
    db.update_job(job.id, status=JobStatus.RENDERING)
    with db.session() as s:
        for i, rs in enumerate([RenderStatus.DONE, RenderStatus.RENDERING, RenderStatus.PENDING], 1):
            s.add(
                Clip(
                    job_id=job.id,
                    position=i,
                    start=0,
                    end=30,
                    title="t",
                    hook="h",
                    description="",
                    hashtags=[],
                    score=5,
                    reason="",
                    render_status=rs,
                )
            )
        s.commit()
    return job


def test_mark_stopped(job_with_clips):
    pipeline.mark_stopped(job_with_clips.id)
    assert db.get_job(job_with_clips.id).status == JobStatus.CANCELLED
    done, rendering, pending = db.job_clips(job_with_clips.id)
    assert done.render_status == RenderStatus.DONE  # o que estava pronto continua pronto
    for c in (rendering, pending):
        assert c.render_status == RenderStatus.ERROR and c.render_error == pipeline.STOPPED
    assert not JobStatus.CANCELLED.running


def test_mark_stopped_keeps_finished_job_status(job_with_clips):
    db.update_job(job_with_clips.id, status=JobStatus.DONE)
    pipeline.mark_stopped(job_with_clips.id)
    assert db.get_job(job_with_clips.id).status == JobStatus.DONE


def test_queued_task_is_skipped_after_stop(job_with_clips):
    calls = []
    tok = cancel.token(job_with_clips.id)
    cancel.request(job_with_clips.id)
    worker._guard(job_with_clips.id, tok, lambda: calls.append(1))
    assert calls == []
    assert db.get_job(job_with_clips.id).status == JobStatus.CANCELLED


def test_guard_marks_stopped_when_task_is_cancelled(job_with_clips):
    def task():
        raise cancel.Cancelled()

    worker._guard(job_with_clips.id, cancel.token(job_with_clips.id), task)
    assert db.get_job(job_with_clips.id).status == JobStatus.CANCELLED
