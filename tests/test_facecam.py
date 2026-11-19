import pytest

from cortago import config, db, facecam, pipeline, render
from cortago.db import Clip, ClipStatus, JobStatus, RenderStatus

RECT = {"x": 0.75, "y": 0.05, "w": 0.2, "h": 0.25}


def test_validate_normalizes_and_rejects():
    assert facecam.validate(None) is None
    assert facecam.validate({"x": "0.75", "y": 0.05, "w": 0.2, "h": 0.25}) == RECT
    # Passa da borda: corta no limite do quadro.
    assert facecam.validate({"x": 0.9, "y": 0.9, "w": 0.5, "h": 0.5}) == {
        "x": 0.9,
        "y": 0.9,
        "w": 0.1,
        "h": 0.1,
    }
    with pytest.raises(ValueError):
        facecam.validate({"x": 0.1, "y": 0.1, "w": 0.01, "h": 0.2})
    with pytest.raises(ValueError):
        facecam.validate({"x": "a", "y": 0, "w": 1, "h": 1})


def test_crop_filter():
    assert facecam.crop_filter(RECT) == "crop=w=iw*0.2000:h=ih*0.2500:x=iw*0.7500:y=ih*0.0500,"


def test_speaker_filter_layouts():
    W, H = config.OUT_W, config.OUT_H
    assert render._speaker_filter("blur", "[v]", "[o]") == render._layout_filter("blur", "[v]", "[o]")
    none = render._speaker_filter("blur", "[v]", "[o]", render.Facecam(RECT, "none"))
    assert none == render._layout_filter("blur", "[v]", "[o]")

    cam = render._speaker_filter("blur", "[v]", "[o]", render.Facecam(RECT, "camera"))
    assert cam.startswith("[v]crop=w=iw*0.2000") and f"crop={W}:{H}" in cam

    split = render._speaker_filter("blur", "[v]", "[o]", render.Facecam(RECT, "dividida"))
    top = int(H * facecam.CAM_SHARE) // 2 * 2
    assert f"crop={W}:{top}" in split and f"crop={W}:{H - top}" in split and "vstack=inputs=2[o]" in split


def test_gameplay_split_uses_facecam_on_top():
    bg = render.Gameplay(path=config.ROOT / "x.mp4", mode="dividida")
    f = render._gameplay_filter(bg, "[1:v]", "[v]", "blur", 30, "[o]", render.Facecam(RECT))
    assert "[v]crop=w=iw*0.2000" in f
    alt = render._gameplay_filter(
        render.Gameplay(path=config.ROOT / "x.mp4", spans=[(3, 6)]),
        "[1:v]",
        "[v]",
        "blur",
        30,
        "[o]",
        render.Facecam(RECT),
    )
    assert "[camsrc]crop=w=iw*0.2000" in alt and "enable='between(t,3.000,6.000)'" in alt


@pytest.fixture
def job_with_clips():
    job = pipeline.create_job("https://x")
    db.update_job(job.id, status=JobStatus.DONE, source_file="source.mp4")
    with db.session() as s:
        for i, st in enumerate([ClipStatus.SUGGESTED, ClipStatus.DISCARDED], 1):
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
                    status=st,
                    render_status=RenderStatus.DONE,
                )
            )
        s.commit()
    return job


def test_set_facecam_marks_clips_for_rerender(job_with_clips):
    pipeline.set_facecam(job_with_clips.id, RECT)
    assert db.get_job(job_with_clips.id).facecam == RECT
    kept, discarded = db.job_clips(job_with_clips.id)
    assert kept.facecam_layout == "dividida" and kept.render_status == RenderStatus.PENDING
    assert discarded.render_status == RenderStatus.DONE  # descartado não renderiza

    pipeline.set_facecam(job_with_clips.id, None)
    assert db.get_job(job_with_clips.id).facecam is None
    assert all(c.facecam_layout == "none" for c in db.job_clips(job_with_clips.id))
