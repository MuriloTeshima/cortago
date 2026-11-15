import pytest

from cortago import config, db, pipeline
from cortago.db import ClipStatus, JobStatus, RenderStatus
from cortago.download import SourceInfo
from cortago.highlights import ClipSuggestion
from cortago.transcribe import Segment, Transcript, Word


class FakeUsage:
    input_tokens = 100
    output_tokens = 20


@pytest.fixture
def fakes(monkeypatch):
    calls = {"download": 0, "select": 0, "render": [], "music": [], "volume": []}

    def fetch(source, job_dir):
        calls["download"] += 1
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "source.mp4").write_bytes(b"x")
        return SourceInfo(
            title="Vídeo", channel="Canal", url="https://x", duration=120, path=job_dir / "source.mp4"
        )

    def transcribe(video, cache, language=None):
        words = [Word(text=f"p{i}", start=i, end=i + 0.8) for i in range(100)]
        return Transcript(language="pt", segments=[Segment(start=0, end=100, text="", words=words)])

    def pick_clips(info, tr, count, min_s, max_s):
        calls["select"] += 1
        sugs = [
            ClipSuggestion(
                start=10, end=40, title="A", hook="h", description="d", hashtags=["gta6"], score=9, reason="r"
            ),
            ClipSuggestion(
                start=50, end=80, title="B", hook="h", description="d", hashtags=[], score=7, reason="r"
            ),
        ]
        return sugs[:count], FakeUsage()

    def render_clip(source, start, end, ass, out, layout, music=None, music_offset=0.0, music_volume=None):
        calls["render"].append((start, end))
        calls["music"].append(music.name if music else None)
        calls["volume"].append(music_volume)
        out.write_bytes(b"mp4")

    monkeypatch.setattr(pipeline.download, "fetch", fetch)
    monkeypatch.setattr(pipeline.transcribe, "transcribe", transcribe)
    monkeypatch.setattr(pipeline.highlights, "pick_clips", pick_clips)
    monkeypatch.setattr(pipeline.render, "render_clip", render_clip)
    monkeypatch.setattr(pipeline.render, "media_duration", lambda path: 180.0)
    monkeypatch.setattr(pipeline.render, "measure_loudness", lambda path, start, duration: calls["loudness"])
    calls["loudness"] = -15.0
    return calls


def test_run_job_full(fakes):
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    job = pipeline.run_job(job.id)

    assert job.status == JobStatus.DONE
    assert (job.title, job.channel, job.input_tokens) == ("Vídeo", "Canal", 100)
    clips = db.job_clips(job.id)
    assert [c.title for c in clips] == ["A", "B"]
    assert all(c.render_status == RenderStatus.DONE and c.render_version == 1 for c in clips)
    text = pipeline.clip_path(job, clips[0], "txt").read_text()
    assert "Créditos: Canal — https://x" in text and "#gta6" in text


def test_run_job_resumes_without_redoing_steps(fakes):
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    pipeline.run_job(job.id)
    pipeline.run_job(job.id)
    assert fakes["download"] == 1
    assert fakes["select"] == 1
    assert len(fakes["render"]) == 2


def test_discarded_clips_are_not_rendered(fakes, monkeypatch):
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    pipeline.run_job(job.id)
    first, second = db.job_clips(job.id)
    db.update_clip(first.id, status=ClipStatus.DISCARDED, render_status=RenderStatus.PENDING)
    db.update_clip(second.id, render_status=RenderStatus.PENDING)
    fakes["render"].clear()
    pipeline.run_job(job.id)
    assert fakes["render"] == [(second.start, second.end)]


def test_reselect_replaces_clips(fakes):
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    pipeline.run_job(job.id)
    old_ids = {c.id for c in db.job_clips(job.id)}
    job = pipeline.run_job(job.id, reselect=True)
    assert fakes["select"] == 2
    assert old_ids.isdisjoint({c.id for c in db.job_clips(job.id)})
    assert job.input_tokens == 200


def test_error_is_recorded(fakes, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("sem internet")

    monkeypatch.setattr(pipeline.download, "fetch", boom)
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    with pytest.raises(RuntimeError):
        pipeline.run_job(job.id)
    assert db.get_job(job.id).status == JobStatus.ERROR
    assert "sem internet" in db.get_job(job.id).error


def test_create_job_validates():
    with pytest.raises(ValueError):
        pipeline.create_job("x", layout="zoom")
    with pytest.raises(ValueError):
        pipeline.create_job("x", min_seconds=60, max_seconds=30)


def add_tracks(*names, credits=None):
    config.MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        (config.MUSIC_DIR / name).write_bytes(b"audio")
    for name, text in (credits or {}).items():
        (config.MUSIC_DIR / name).with_suffix(".txt").write_text(text)


def test_music_is_picked_and_kept(fakes):
    add_tracks("a.mp3", "b.mp3")
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    pipeline.run_job(job.id)
    tracks = [c.music_track for c in db.job_clips(job.id)]
    assert all(t in ("a.mp3", "b.mp3") for t in tracks)
    assert fakes["music"] == tracks

    # re-renderizar mantém a mesma faixa
    clip = db.job_clips(job.id)[0]
    pipeline.render_clip(clip.id)
    assert fakes["music"][-1] == clip.music_track


def test_job_without_music(fakes):
    add_tracks("a.mp3")
    job = pipeline.create_job("https://youtube.com/watch?v=abc", music=False)
    pipeline.run_job(job.id)
    assert fakes["music"] == [None, None]
    assert all(c.music_track is None for c in db.job_clips(job.id))


def test_empty_library_renders_without_music_and_retries_later(fakes):
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    pipeline.run_job(job.id)
    assert fakes["music"] == [None, None]
    clip = db.job_clips(job.id)[0]
    assert clip.music_track is None  # continua "a escolher"

    add_tracks("a.mp3")
    assert pipeline.render_clip(clip.id).music_track == "a.mp3"


def test_explicit_no_music(fakes):
    add_tracks("a.mp3")
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    pipeline.run_job(job.id)
    clip = db.update_clip(db.job_clips(job.id)[0].id, music_track="")
    pipeline.render_clip(clip.id)
    assert fakes["music"][-1] is None


def test_missing_track_is_a_clear_error(fakes):
    add_tracks("a.mp3")
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    pipeline.run_job(job.id)
    clip = db.job_clips(job.id)[0]
    (config.MUSIC_DIR / "a.mp3").unlink()
    with pytest.raises(FileNotFoundError):
        pipeline.render_clip(clip.id)
    failed = db.job_clips(job.id)[0]
    assert failed.render_status == RenderStatus.ERROR
    assert "a.mp3" in failed.render_error


def test_music_credit_goes_to_text(fakes):
    add_tracks("a.mp3", credits={"a.mp3": "Faixa X por Fulano (CC BY)"})
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    job = pipeline.run_job(job.id)
    clip = db.job_clips(job.id)[0]
    assert "Música: Faixa X por Fulano (CC BY)" in pipeline.clip_path(job, clip, "txt").read_text()


def test_music_volume_follows_video_loudness_and_level(fakes):
    add_tracks("a.mp3")
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    pipeline.run_job(job.id)
    normal = fakes["volume"][0]

    clip = db.job_clips(job.id)[0]
    fakes["loudness"] = -27.0  # vídeo 12 dB mais baixo
    pipeline.render_clip(clip.id)
    assert fakes["volume"][-1] < normal / 3

    fakes["loudness"] = -15.0
    db.update_clip(clip.id, music_level=50)
    pipeline.render_clip(clip.id)
    assert abs(fakes["volume"][-1] - normal / 2) < 1e-9
