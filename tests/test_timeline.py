import pytest

from cortago import config, db, editing, pipeline, timeline
from cortago.db import Clip, JobStatus, RenderStatus
from cortago.transcribe import Segment, Transcript, Word

# ---------- regras puras ----------


def test_word_fixes_are_applied_by_position():
    words = [Word(text="loading", start=1.0, end=1.4), Word(text="cyberpunk", start=2.004, end=2.5)]
    fixed = timeline.apply_word_fixes(words, {"2.00": "Cyberpunk"})
    assert [w.text for w in fixed] == ["loading", "Cyberpunk"]
    assert timeline.apply_word_fixes(words, None) is words


def test_validate_segments_sorts_and_rejects_bad_input():
    assert timeline.validate_segments([(5, 8), (1, 3)], 10) == [(1, 3), (5, 8)]
    for bad in ([], [(1, 3), (2, 4)], [(-1, 2)], [(1, 1.05)], [(8, 12)]):
        with pytest.raises(ValueError):
            timeline.validate_segments(bad, 10)


def test_validate_word_fixes():
    assert timeline.validate_word_fixes({"2.004": "  Vice   City "}) == {"2.00": "Vice City"}
    with pytest.raises(ValueError):
        timeline.validate_word_fixes({"1.00": "  "})
    with pytest.raises(ValueError):
        timeline.validate_word_fixes({"1.00": "x" * 41})


def test_display_window_has_context_and_respects_limits():
    assert timeline.display_window(30, 60, 300) == (15, 75)
    assert timeline.display_window(5, 60, 70) == (0, 70)


# ---------- salvar na edição ----------


@pytest.fixture
def clip():
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    db.update_job(job.id, status=JobStatus.DONE, duration=300)
    with db.session() as s:
        c = Clip(
            job_id=job.id,
            position=1,
            start=10,
            end=40,
            title="t",
            hook="h",
            description="",
            hashtags=[],
            score=8,
            reason="",
            render_status=RenderStatus.DONE,
        )
        s.add(c)
        s.commit()
        s.refresh(c)
    return c


def test_update_timeline_sets_cut_from_segments(clip):
    r = editing.update_timeline(clip.id, segments=[(12, 20), (25, 38)], word_fixes={"13.5": "GTA"})
    assert r.rerender
    assert (r.clip.start, r.clip.end) == (12, 38)
    assert r.clip.edit == {"segments": [[12, 20], [25, 38]], "words": {"13.50": "GTA"}}
    # salvar o mesmo de novo não renderiza
    assert not editing.update_timeline(
        clip.id, segments=[(12, 20), (25, 38)], word_fixes={"13.5": "GTA"}
    ).rerender


def test_update_timeline_limits(clip):
    with pytest.raises(editing.EditError, match="sobrepor"):
        editing.update_timeline(clip.id, segments=[(12, 20), (19, 30)])
    with pytest.raises(editing.EditError, match="máximo"):
        editing.update_timeline(clip.id, segments=[(0, 100), (101, 200)])
    with pytest.raises(editing.EditError, match="fora do vídeo"):
        editing.update_timeline(clip.id, segments=[(290, 320)])


def test_reset_timeline(clip):
    assert not editing.reset_timeline(clip.id).rerender  # nada a restaurar
    editing.update_timeline(clip.id, segments=[(12, 20)])
    r = editing.reset_timeline(clip.id)
    assert r.rerender and r.clip.edit is None


# ---------- render usa os ajustes ----------


def test_render_uses_manual_segments_and_word_fixes(clip, monkeypatch, tmp_path):
    job = db.get_job(clip.job_id)
    src = pipeline.job_dir(job) / "source.mp4"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"x")
    db.update_job(job.id, source_file="source.mp4")
    words = [Word(text="loading", start=13.0, end=13.5), Word(text="fim", start=30.0, end=30.4)]
    monkeypatch.setattr(
        pipeline.transcribe,
        "transcribe",
        lambda *a, **k: Transcript(language="pt", segments=[Segment(start=13, end=31, text="", words=words)]),
    )
    seen = {}
    monkeypatch.setattr(
        pipeline.subtitles, "write_ass", lambda w, *a, **k: seen.update(words=w, segments=k["segments"])
    )
    monkeypatch.setattr(
        pipeline.render, "render_clip", lambda *a, **k: seen.update(render_segments=k["segments"])
    )
    monkeypatch.setattr(pipeline.render, "thumbnail", lambda *a: None)
    monkeypatch.setattr(
        pipeline.render, "detect_quiet", lambda *a: pytest.fail("não deveria detectar silêncio")
    )
    monkeypatch.setattr(config, "MUSIC_DIR", tmp_path / "sem-musica")

    editing.update_timeline(clip.id, segments=[(12, 20), (25, 38)], word_fixes={"13.00": "Loading"})
    db.update_clip(clip.id, jump_cuts=True)  # trechos manuais têm prioridade sobre o corte automático
    pipeline.render_clip(clip.id)

    assert seen["render_segments"] == [(12, 20), (25, 38)]
    assert seen["segments"] == [(12, 20), (25, 38)]
    assert [w.text for w in seen["words"]] == ["Loading", "fim"]
