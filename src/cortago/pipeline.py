"""Orquestra as etapas de um job e grava o progresso no banco.

Usado pela CLI (síncrono) e pela interface web (via worker em segundo plano).
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

from sqlmodel import delete

from cortago import (
    config,
    db,
    download,
    effects,
    highlights,
    music,
    post_info,
    render,
    subtitles,
    timecode,
    transcribe,
)
from cortago.db import Clip, ClipStatus, Job, JobStatus, RenderStatus

Log = Callable[[str], None]


def _noop(_: str) -> None:
    pass


def job_dir(job: Job) -> Path:
    return config.JOBS_DIR / job.dir_name


def clip_path(job: Job, clip: Clip, ext: str = "mp4") -> Path:
    return job_dir(job) / "clips" / f"{clip.file_stem}.{ext}"


def clip_text(clip: Clip, job: Job) -> str:
    """Título + descrição (com créditos e hashtags) num texto só, salvo no .txt ao lado do vídeo."""
    info = post_info.build(clip, job)
    return f"{info.title}\n\n{info.description}\n"


def write_clip_text(job: Job, clip: Clip) -> None:
    path = clip_path(job, clip, "txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(clip_text(clip, job), encoding="utf-8")


MIN_RANGE_SECONDS = 30  # trecho menor que isso não rende cortes


def create_job(
    source: str,
    *,
    layout: str = "blur",
    max_clips: int = 5,
    min_seconds: int = 20,
    max_seconds: int = 60,
    language: str | None = None,
    music: bool = True,
    range_start: float | None = None,
    range_end: float | None = None,
) -> Job:
    if layout not in render.LAYOUTS:
        raise ValueError(f"layout inválido: {layout}")
    if min_seconds >= max_seconds:
        raise ValueError("a duração mínima precisa ser menor que a máxima")
    if range_start is not None and range_start < 0:
        raise ValueError("o início do trecho não pode ser negativo")
    if range_end is not None and range_end - (range_start or 0) < max(min_seconds, MIN_RANGE_SECONDS):
        raise ValueError(f"o trecho precisa ter pelo menos {max(min_seconds, MIN_RANGE_SECONDS)}s")
    with db.session() as s:
        job = Job(
            source=source.strip(),
            layout=layout,
            max_clips=max_clips,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            language=language or None,
            music=music,
            range_start=range_start or None,
            range_end=range_end,
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        return job


def run_job(job_id: int, log: Log = _noop, reselect: bool = False) -> Job:
    """Executa (ou retoma) todas as etapas. Etapas já concluídas são reaproveitadas."""
    try:
        job = _download(job_id, log)
        tr = _transcribe(job, log)
        if reselect or not db.job_clips(job_id):
            _select(job, tr, log)
        db.update_job(job_id, status=JobStatus.RENDERING)
        for clip in db.job_clips(job_id):
            if clip.status != ClipStatus.DISCARDED and clip.render_status != RenderStatus.DONE:
                log(f"Renderizando corte {clip.position}...")
                render_clip(clip.id)  # type: ignore[arg-type]
        log("Pronto.")
        return db.update_job(job_id, status=JobStatus.DONE, error=None)
    except Exception as exc:
        db.update_job(job_id, status=JobStatus.ERROR, error=describe_error(exc))
        raise


def _download(job_id: int, log: Log) -> Job:
    with db.session() as s:
        job = s.get(Job, job_id)
    assert job is not None
    if job.source_file and (job_dir(job) / job.source_file).exists():
        return job
    db.update_job(job_id, status=JobStatus.DOWNLOADING, error=None)
    section = (job.range_start or 0.0, job.range_end) if (job.range_start or job.range_end) else None
    log("Baixando trecho do vídeo..." if section else "Baixando vídeo...")
    info = download.fetch(job.source, job_dir(job), section)
    if job.range_start and job.range_start >= info.duration:
        raise ValueError(
            f"o trecho começa em {timecode.format(job.range_start)}, mas o vídeo tem só {timecode.format(info.duration)}"
        )
    return db.update_job(
        job_id,
        title=info.title,
        channel=info.channel,
        url=info.url,
        duration=info.duration,
        source_file=info.path.name,
        source_offset=info.offset,
    )


def _transcribe(job: Job, log: Log) -> transcribe.Transcript:
    db.update_job(job.id, status=JobStatus.TRANSCRIBING)  # type: ignore[arg-type]
    log("Transcrevendo...")
    return transcribe.transcribe(
        job_dir(job) / job.source_file,  # type: ignore[operator]
        job_dir(job) / "transcript.json",
        job.language,
        window=job.window(),
    )


def _select(job: Job, tr: transcribe.Transcript, log: Log) -> None:
    db.update_job(job.id, status=JobStatus.SELECTING)  # type: ignore[arg-type]
    log(f"Claude escolhendo cortes ({config.CLAUDE_MODEL})...")
    info = download.SourceInfo(
        title=job.title or "",
        channel=job.channel or "",
        url=job.url or "",
        # Com trecho, o Claude só vê (e só precisa saber) a duração do trecho.
        duration=(job.range_end or job.duration or 0) - (job.range_start or 0),
        path=job_dir(job) / (job.source_file or ""),
    )
    suggestions, usage = highlights.pick_clips(info, tr, job.max_clips, job.min_seconds, job.max_seconds)

    clips_dir = job_dir(job) / "clips"
    if clips_dir.exists():
        for f in clips_dir.iterdir():
            f.unlink()
    with db.session() as s:
        s.exec(delete(Clip).where(Clip.job_id == job.id))  # type: ignore[arg-type]
        for i, sug in enumerate(suggestions, 1):
            s.add(Clip(job_id=job.id, position=i, **sug.model_dump(), **effects.defaults()))  # type: ignore[arg-type]
        s.commit()
    db.update_job(
        job.id,  # type: ignore[arg-type]
        input_tokens=job.input_tokens + usage.input_tokens,
        output_tokens=job.output_tokens + usage.output_tokens,
    )
    log(f"{len(suggestions)} cortes escolhidos.")


def render_clip(clip_id: int) -> Clip:
    with db.session() as s:
        clip = s.get(Clip, clip_id)
        assert clip is not None
        job = s.get(Job, clip.job_id)
        assert job is not None and job.source_file

    db.update_clip(clip_id, render_status=RenderStatus.RENDERING, render_error=None)
    try:
        tr = transcribe.transcribe(
            job_dir(job) / job.source_file,
            job_dir(job) / "transcript.json",
            job.language,
            window=job.window(),
        )
        ass = clip_path(job, clip, "ass")
        ass.parent.mkdir(parents=True, exist_ok=True)
        source = job_dir(job) / job.source_file
        fx = effects.Effects.from_clip(clip)
        clip = _ensure_music_track(clip, job)
        track = _music_file(clip)
        loudness = (
            render.measure_loudness(source, clip.start, clip.duration) if (track or fx.jump_cuts) else None
        )
        segments = None
        if fx.jump_cuts:
            quiet = render.detect_quiet(
                source, clip.start, clip.duration, effects.quiet_threshold_db(loudness)
            )
            segments = effects.speech_segments(tr.words, clip.start, clip.end, quiet)
        subtitles.write_ass(
            tr.words, clip.start, clip.end, clip.hook, ass, segments=segments, hook_anim=fx.hook_anim
        )
        render.render_clip(
            source,
            clip.start,
            clip.end,
            ass,
            clip_path(job, clip),
            job.layout,
            music=track,
            music_offset=music.offset(render.media_duration(track), clip.duration, clip.id) if track else 0.0,  # type: ignore[arg-type]
            music_volume=render.auto_music_volume(loudness, level=clip.music_level) if track else None,
            segments=segments,
            fx=fx,
        )
        render.thumbnail(clip_path(job, clip), clip_path(job, clip, "jpg"))
        write_clip_text(job, clip)
    except Exception as exc:
        db.update_clip(clip_id, render_status=RenderStatus.ERROR, render_error=describe_error(exc))
        raise
    return db.update_clip(clip_id, render_status=RenderStatus.DONE, render_version=clip.render_version + 1)


def _ensure_music_track(clip: Clip, job: Job) -> Clip:
    """Sorteia a música na primeira renderização. Depois fica fixa até o usuário trocar."""
    if clip.music_track is not None or not job.music:
        return clip
    track = music.pick(clip.id)  # type: ignore[arg-type]
    if track is None:  # biblioteca vazia: tenta de novo quando houver músicas
        return clip
    return db.update_clip(clip.id, music_track=track)  # type: ignore[arg-type]


def _music_file(clip: Clip):
    if not clip.music_track:
        return None
    path = music.path(clip.music_track)
    if path is None:
        raise FileNotFoundError(
            f"Música '{clip.music_track}' não está mais em {config.MUSIC_DIR}. Escolha outra na edição do corte."
        )
    return path


def describe_error(exc: Exception) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        tool = Path(str(exc.cmd[0])).name if exc.cmd else "comando"
        stderr = (exc.stderr or "").strip().splitlines()[-3:] if isinstance(exc.stderr, str) else []
        return f"{tool} falhou (código {exc.returncode})" + (": " + " | ".join(stderr) if stderr else "")
    return f"{type(exc).__name__}: {exc}"
