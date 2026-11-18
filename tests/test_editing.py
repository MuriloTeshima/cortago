import pytest

from cortago import config, db, editing, effects, pipeline
from cortago.db import Clip, ClipStatus, JobStatus, RenderStatus


@pytest.fixture
def clip():
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    job = db.update_job(job.id, status=JobStatus.DONE, title="Live", channel="Canal", duration=300)
    with db.session() as s:
        c = Clip(
            job_id=job.id,
            position=1,
            start=10,
            end=40,
            title="Detalhe",
            hook="olha",
            description="d",
            hashtags=["gta6"],
            score=8,
            reason="bom",
            render_status=RenderStatus.DONE,
            render_version=1,
        )
        s.add(c)
        s.commit()
        s.refresh(c)
    return c


def library(*names):
    config.MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        (config.MUSIC_DIR / name).write_bytes(b"audio")


def reload(clip_id):
    with db.session() as s:
        return s.get(Clip, clip_id)


# ---------- texto ----------


def test_text_without_hook_change_does_not_rerender(clip):
    r = editing.update_text(
        clip.id, title=" Novo ", hook="olha", description="x", hashtags="#gta6, #rockstar"
    )
    assert not r.rerender
    c = reload(clip.id)
    assert (c.title, c.description, c.hashtags) == ("Novo", "x", ["gta6", "rockstar"])
    # o .txt ao lado do vídeo acompanha o texto novo mesmo sem render
    job = db.get_job(c.job_id)
    assert "x" in pipeline.clip_path(job, c, "txt").read_text(encoding="utf-8")


def test_hook_change_rerenders(clip):
    assert editing.update_text(clip.id, title="t", hook="novo gancho", description="", hashtags="").rerender


def test_empty_title_is_rejected(clip):
    with pytest.raises(editing.EditError):
        editing.update_text(clip.id, title="  ", hook="olha", description="", hashtags="")


# ---------- corte ----------


def test_cut_change_rerenders(clip):
    r = editing.update_cut(clip.id, start=12, end=38)
    assert r.rerender and (reload(clip.id).start, reload(clip.id).end) == (12, 38)


def test_same_cut_does_not_rerender(clip):
    assert not editing.update_cut(clip.id, start=10, end=40).rerender


@pytest.mark.parametrize(("start", "end"), [(40, 10), (0, 250), (200, 310)])
def test_invalid_cut(clip, start, end):
    with pytest.raises(editing.EditError):
        editing.update_cut(clip.id, start=start, end=end)


def test_cut_uses_original_video_time(clip):
    db.update_job(clip.job_id, source_offset=4800, range_start=4800, range_end=7200)
    editing.update_cut(clip.id, start=4815, end=4840)
    assert (reload(clip.id).start, reload(clip.id).end) == (15, 40)
    with pytest.raises(editing.EditError, match="antes do trecho"):
        editing.update_cut(clip.id, start=100, end=120)
    with pytest.raises(editing.EditError, match="passa do fim"):
        editing.update_cut(clip.id, start=7190, end=7210)


# ---------- música ----------


def test_music_track_and_level(clip):
    library("a.mp3", "b.mp3")
    assert editing.update_music(clip.id, track="b.mp3").rerender
    assert not editing.update_music(clip.id, track="b.mp3").rerender  # sem mudança
    assert editing.update_music(clip.id, track="").rerender  # sem música
    assert reload(clip.id).music_track == ""
    assert editing.update_music(clip.id, track=None, level=60).rerender  # None = mantém a faixa
    assert (reload(clip.id).music_track, reload(clip.id).music_level) == ("", 60)


@pytest.mark.parametrize(
    ("track", "level"), [("../../cortago.db", None), ("nao-existe.mp3", None), (None, 500)]
)
def test_invalid_music(clip, track, level):
    library("a.mp3")
    with pytest.raises(editing.EditError):
        editing.update_music(clip.id, track=track, level=level)


def test_nudge_music_level_is_clamped(clip):
    library("a.mp3")
    db.update_clip(clip.id, music_track="a.mp3")
    renders = [editing.nudge_music_level(clip.id, -25).rerender for _ in range(6)]
    assert reload(clip.id).music_level == 0
    assert renders == [True, True, True, True, False, False]  # 75 → 50 → 25 → 0, depois nada muda


def test_nudge_without_music(clip):
    with pytest.raises(editing.EditError, match="não tem música"):
        editing.nudge_music_level(clip.id, 25)


# ---------- efeitos ----------


def test_effects(clip):
    fx = effects.Effects(jump_cuts=True, intro_zoom="forte", hook_sfx="pop")
    assert editing.update_effects(clip.id, fx).rerender
    assert effects.Effects.from_clip(reload(clip.id)) == fx
    assert not editing.update_effects(clip.id, fx).rerender


# ---------- status e navegação ----------


def test_status(clip):
    assert not editing.set_status(clip.id, ClipStatus.APPROVED).rerender
    db.update_clip(clip.id, render_status=RenderStatus.ERROR)
    assert editing.set_status(clip.id, ClipStatus.SUGGESTED).rerender  # voltou a valer e não tem vídeo
    assert not editing.set_status(clip.id, ClipStatus.DISCARDED).rerender


def test_neighbors(clip):
    with db.session() as s:
        for pos in (2, 3):
            s.add(
                Clip(
                    job_id=clip.job_id,
                    position=pos,
                    start=0,
                    end=20,
                    title=f"c{pos}",
                    hook="",
                    description="",
                    hashtags=[],
                    score=5,
                    reason="",
                )
            )
        s.commit()
    clips = db.job_clips(clip.job_id)
    assert editing.neighbors(clips[0]) == (None, clips[1])
    prev, nxt = editing.neighbors(clips[1])
    assert (prev.id, nxt.id) == (clips[0].id, clips[2].id)
    assert editing.neighbors(clips[2])[1] is None


def test_missing_clip():
    with pytest.raises(editing.EditError):
        editing.update_cut(999, start=0, end=10)
