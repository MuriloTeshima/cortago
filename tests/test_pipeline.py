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

    def fetch(source, job_dir, section=None):
        calls.setdefault("section", []).append(section)
        calls["download"] += 1
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "source.mp4").write_bytes(b"x")
        return SourceInfo(
            title="Vídeo", channel="Canal", url="https://x", duration=120, path=job_dir / "source.mp4"
        )

    def transcribe(video, cache, language=None, window=None):
        calls.setdefault("window", []).append(window)
        words = [Word(text=f"p{i}", start=i, end=i + 0.8) for i in range(100)]
        return Transcript(language="pt", segments=[Segment(start=0, end=100, text="", words=words)])

    def pick_clips(info, tr, count, min_s, max_s, gameplay=False):
        calls["select"] += 1
        calls.setdefault("gameplay_prompt", []).append(gameplay)
        sugs = [
            ClipSuggestion(
                start=10,
                end=40,
                title="A",
                hook="h",
                description="d",
                hashtags=["gta6"],
                score=9,
                reason="r",
                gameplay=[(20, 28)] if gameplay else None,
            ),
            ClipSuggestion(
                start=50, end=80, title="B", hook="h", description="d", hashtags=[], score=7, reason="r"
            ),
        ]
        return sugs[:count], FakeUsage()

    def render_clip(
        source,
        start,
        end,
        ass,
        out,
        layout,
        music=None,
        music_offset=0.0,
        music_volume=None,
        segments=None,
        fx=None,
        gameplay=None,
    ):
        calls["render"].append((start, end))
        calls.setdefault("gameplay", []).append(gameplay)
        calls.setdefault("segments", []).append(segments)
        calls.setdefault("fx", []).append(fx)
        calls["music"].append(music.name if music else None)
        calls["volume"].append(music_volume)
        out.write_bytes(b"mp4")

    def fetch_gameplay(source, folder):
        calls["gameplay_download"] = calls.get("gameplay_download", 0) + 1
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "gp.mp4"
        path.write_bytes(b"gp")
        return path

    monkeypatch.setattr(pipeline.download, "fetch", fetch)
    monkeypatch.setattr(pipeline.download, "fetch_gameplay", fetch_gameplay)
    monkeypatch.setattr(pipeline.transcribe, "transcribe", transcribe)
    monkeypatch.setattr(pipeline.highlights, "pick_clips", pick_clips)
    monkeypatch.setattr(pipeline.render, "render_clip", render_clip)
    monkeypatch.setattr(pipeline.render, "media_duration", lambda path: 180.0)
    monkeypatch.setattr(pipeline.render, "thumbnail", lambda video, out: out.write_bytes(b"jpg"))
    monkeypatch.setattr(pipeline.render, "measure_loudness", lambda path, start, duration: calls["loudness"])
    calls["loudness"] = -15.0
    calls["quiet"] = []
    monkeypatch.setattr(
        pipeline.render, "detect_quiet", lambda path, start, duration, threshold: calls["quiet"]
    )
    return calls


def test_run_job_full(fakes):
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    job = pipeline.run_job(job.id)

    assert job.status == JobStatus.DONE
    assert (job.title, job.channel, job.input_tokens) == ("Vídeo", "Canal", 100)
    clips = db.job_clips(job.id)
    assert [c.title for c in clips] == ["A", "B"]
    assert all(c.render_status == RenderStatus.DONE and c.render_version == 1 for c in clips)
    text = pipeline.clip_path(job, clips[0], "txt").read_text(encoding="utf-8")
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
    assert "Música: Faixa X por Fulano (CC BY)" in pipeline.clip_path(job, clip, "txt").read_text(
        encoding="utf-8"
    )


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


def test_new_clips_get_effect_defaults_from_config(fakes, monkeypatch):
    monkeypatch.setattr(config, "FX_JUMP_CUTS", True)
    monkeypatch.setattr(config, "FX_INTRO_ZOOM", "forte")
    monkeypatch.setattr(config, "FX_HOOK_SFX", "pop")
    monkeypatch.setattr(config, "FX_PROGRESS_BAR", True)
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    pipeline.run_job(job.id)
    clip = db.job_clips(job.id)[0]
    assert (clip.jump_cuts, clip.intro_zoom, clip.hook_sfx, clip.progress_bar, clip.hook_anim) == (
        True,
        "forte",
        "pop",
        True,
        False,
    )
    fx = fakes["fx"][0]
    assert (fx.intro_zoom, fx.hook_sfx, fx.progress_bar) == ("forte", "pop", True)


def test_jump_cuts_remove_only_quiet_pauses(fakes, monkeypatch):
    monkeypatch.setattr(config, "FX_JUMP_CUTS", True)
    # palavras a cada 1 s com 0,2 s de pausa; um silêncio real de 13,0 a 15,0
    fakes["quiet"] = [(13.0, 15.0)]
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    pipeline.run_job(job.id)
    segments = fakes["segments"][0]
    assert segments is not None and len(segments) >= 1
    # nenhuma pausa sem silêncio foi cortada: os trechos cobrem tudo menos o miolo do silêncio detectado
    removed = (40 - 10) - sum(b - a for a, b in segments)
    assert removed < 2.0


def test_jump_cuts_off_keeps_whole_clip(fakes):
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    pipeline.run_job(job.id)
    assert fakes["segments"] == [None, None]


def test_range_is_passed_to_download_and_transcription(fakes, monkeypatch):
    def fetch(source, job_dir, section=None):
        fakes.setdefault("section", []).append(section)
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "source.mp4").write_bytes(b"x")
        # só o trecho foi baixado: o arquivo começa em 4800 s do original
        return SourceInfo(
            title="Live",
            channel="Canal",
            url="https://youtu.be/abc",
            duration=18000,
            path=job_dir / "source.mp4",
            offset=4800,
        )

    monkeypatch.setattr(pipeline.download, "fetch", fetch)
    job = pipeline.create_job("https://youtu.be/abc", range_start=4800, range_end=7200)
    job = pipeline.run_job(job.id)
    assert fakes["section"][-1] == (4800, 7200)
    assert job.source_offset == 4800
    assert fakes["window"][-1] == (0.0, 2400)  # no relógio do arquivo baixado
    text = pipeline.clip_path(job, db.job_clips(job.id)[0], "txt").read_text(encoding="utf-8")
    assert "https://youtu.be/abc?t=4810s" in text  # corte em 10 s do arquivo = 4810 s da live


def test_range_with_full_download(fakes):
    # o fake baixa o vídeo inteiro (offset 0): o trecho vira janela de transcrição
    job = pipeline.create_job("https://youtube.com/watch?v=abc", range_start=30, range_end=90)
    pipeline.run_job(job.id)
    assert fakes["window"][-1] == (30, 90)


def test_range_validation():
    with pytest.raises(ValueError, match="pelo menos"):
        pipeline.create_job("x", range_start=100, range_end=110)
    with pytest.raises(ValueError, match="negativo"):
        pipeline.create_job("x", range_start=-5)


def test_range_start_after_video_end(fakes):
    job = pipeline.create_job("https://youtube.com/watch?v=abc", range_start=500)  # o vídeo do fake tem 120 s
    with pytest.raises(ValueError, match="começa em"):
        pipeline.run_job(job.id)
    assert db.get_job(job.id).status == JobStatus.ERROR


# ---------- gameplay de fundo ----------


def test_job_with_gameplay_downloads_it_and_asks_claude_for_spans(fakes):
    job = pipeline.create_job("https://x", gameplay_source="https://gameplay")
    pipeline.run_job(job.id)
    job = db.get_job(job.id)
    assert fakes["gameplay_download"] == 1
    assert job.gameplay_file and job.gameplay_file.endswith("gp.mp4")
    assert fakes["gameplay_prompt"] == [True]
    first, second = db.job_clips(job.id)
    assert first.gameplay_mode == "alternar" and first.gameplay_hints == [[20, 28]]
    assert second.gameplay_hints is None
    bg = fakes["gameplay"][0]
    assert bg.mode == "alternar" and bg.path.name == "gp.mp4"
    # Indicação do Claude: 20–28s do arquivo. Sem pontuação, os blocos têm ~8s (17,9–25,9 fica 75% coberto)
    # e o resultado sai no tempo do corte, que começa em 10s.
    assert bg.spans == [(7.9, 15.9)]


def test_job_without_gameplay_renders_without_it(fakes):
    job = pipeline.create_job("https://x")
    pipeline.run_job(job.id)
    assert fakes["gameplay_prompt"] == [False]
    assert fakes["gameplay"] == [None, None]
    assert "gameplay_download" not in fakes
    assert all(c.gameplay_mode == "none" for c in db.job_clips(job.id))


def test_gameplay_mode_from_config(fakes, monkeypatch):
    monkeypatch.setattr(pipeline.config, "GAMEPLAY_MODE", "dividida")
    job = pipeline.create_job("https://x", gameplay_source="https://gameplay")
    pipeline.run_job(job.id)
    assert {c.gameplay_mode for c in db.job_clips(job.id)} == {"dividida"}
    assert fakes["gameplay"][0].spans == [(0.0, 30.0)]


def test_set_gameplay_on_finished_job_rerenders_clips(fakes):
    job = pipeline.create_job("https://x")
    pipeline.run_job(job.id)
    pipeline.set_gameplay(job.id, "https://gameplay")
    clips = db.job_clips(job.id)
    assert all(c.gameplay_mode == "alternar" and c.render_status == "pending" for c in clips)
    pipeline.run_job(job.id)
    assert fakes["gameplay_download"] == 1
    assert fakes["select"] == 1  # não pede cortes de novo
    assert all(g is not None and g.spans for g in fakes["gameplay"][2:])

    pipeline.set_gameplay(job.id, "")
    assert db.get_job(job.id).gameplay_source is None
    assert all(c.gameplay_mode == "none" for c in db.job_clips(job.id))


def test_set_gameplay_rejects_garbage(fakes):
    job = pipeline.create_job("https://x")
    with pytest.raises(ValueError):
        pipeline.set_gameplay(job.id, "isso nao e link")


# ---------- parar ----------


def test_stop_during_render_then_continue(fakes, monkeypatch):
    from cortago import cancel

    job = pipeline.create_job("https://x")
    real_render = pipeline.render.render_clip

    def stop_on_first(*args, **kwargs):
        raise cancel.Cancelled()

    monkeypatch.setattr(pipeline.render, "render_clip", stop_on_first)
    with pytest.raises(cancel.Cancelled):
        pipeline.run_job(job.id)
    assert db.get_job(job.id).status == JobStatus.CANCELLED
    assert all(
        c.render_status == RenderStatus.ERROR and c.render_error == pipeline.STOPPED
        for c in db.job_clips(job.id)
    )

    # "Continuar": refaz só o que faltou (não baixa nem pede cortes de novo).
    monkeypatch.setattr(pipeline.render, "render_clip", real_render)
    pipeline.run_job(job.id)
    assert db.get_job(job.id).status == JobStatus.DONE
    assert fakes["download"] == 1 and fakes["select"] == 1
    assert all(c.render_status == RenderStatus.DONE for c in db.job_clips(job.id))
