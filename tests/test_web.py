import pytest
from fastapi.testclient import TestClient

from cortago import db, pipeline, worker
from cortago.db import Clip, ClipStatus, JobStatus, RenderStatus
from cortago.web.app import app


@pytest.fixture
def queued(monkeypatch):
    """Não processa nada de verdade: só registra o que foi enfileirado."""
    calls = {"jobs": [], "renders": []}
    monkeypatch.setattr(
        worker, "submit_job", lambda job_id, reselect=False: calls["jobs"].append((job_id, reselect))
    )
    monkeypatch.setattr(worker, "submit_render", lambda clip_id: calls["renders"].append(clip_id))
    return calls


@pytest.fixture
def client(queued):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def done_job():
    job = pipeline.create_job("https://youtube.com/watch?v=abc")
    job = db.update_job(job.id, status=JobStatus.DONE, title="Trailer GTA 6", channel="Canal", duration=300)
    with db.session() as s:
        clip = Clip(
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
        s.add(clip)
        s.commit()
        s.refresh(clip)
    return job, clip


def test_index_lists_jobs(client, done_job):
    r = client.get("/")
    assert r.status_code == 200
    assert "Trailer GTA 6" in r.text


def test_create_job_enqueues_and_redirects(client, queued):
    r = client.post(
        "/jobs", data={"source": "https://youtube.com/watch?v=xyz", "max_clips": 3}, follow_redirects=False
    )
    assert r.status_code == 303
    job_id = int(r.headers["location"].rsplit("/", 1)[1])
    assert queued["jobs"] == [(job_id, False)]
    assert db.get_job(job_id).max_clips == 3


def test_create_job_rejects_bad_layout(client):
    r = client.post("/jobs", data={"source": "x", "layout": "zoom"})
    assert r.status_code == 400


def test_job_page_shows_clips(client, done_job):
    job, clip = done_job
    r = client.get(f"/jobs/{job.id}")
    assert r.status_code == 200
    assert "Detalhe" in r.text
    assert f"/media/{job.id}/{clip.id}.mp4?v=1" in r.text
    assert "hx-trigger" not in r.text  # nada rodando, então sem polling


def test_edit_title_only_does_not_rerender(client, queued, done_job):
    job, clip = done_job
    form = {
        "title": "Novo título",
        "hook": "olha",
        "description": "d",
        "hashtags": "#gta6, #rockstar",
        "start": "10.0",
        "end": "40.0",
    }
    r = client.post(f"/clips/{clip.id}", data=form)
    assert r.status_code == 200
    assert queued["renders"] == []
    with db.session() as s:
        updated = s.get(Clip, clip.id)
    assert updated.title == "Novo título"
    assert updated.hashtags == ["gta6", "rockstar"]


def test_edit_times_rerenders(client, queued, done_job):
    _, clip = done_job
    form = {"title": "t", "hook": "olha", "description": "d", "hashtags": "", "start": "12", "end": "38"}
    client.post(f"/clips/{clip.id}", data=form)
    assert queued["renders"] == [clip.id]


@pytest.mark.parametrize(("start", "end"), [("40", "10"), ("0", "250"), ("200", "310")])
def test_edit_rejects_invalid_times(client, done_job, start, end):
    _, clip = done_job
    form = {"title": "t", "hook": "h", "description": "d", "hashtags": "", "start": start, "end": end}
    assert client.post(f"/clips/{clip.id}", data=form).status_code == 400


def test_approve_and_discard(client, done_job):
    _, clip = done_job
    r = client.post(f"/clips/{clip.id}/status", data={"status": "approved"})
    assert "Aprovado" in r.text
    client.post(f"/clips/{clip.id}/status", data={"status": "discarded"})
    with db.session() as s:
        assert s.get(Clip, clip.id).status == ClipStatus.DISCARDED


def test_media_serves_file_and_download(client, done_job):
    job, clip = done_job
    path = pipeline.clip_path(job, clip)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"fake mp4")
    assert client.get(f"/media/{job.id}/{clip.id}.mp4").content == b"fake mp4"
    r = client.get(f"/media/{job.id}/{clip.id}.mp4?download=true")
    assert r.headers["content-disposition"].startswith("attachment")


def test_media_wrong_job_is_404(client, done_job):
    job, clip = done_job
    assert client.get(f"/media/{job.id + 1}/{clip.id}.mp4").status_code == 404


def test_delete_job(client, done_job):
    job, _ = done_job
    r = client.post(f"/jobs/{job.id}/delete")
    assert r.headers["HX-Redirect"] == "/"
    assert db.get_job(job.id) is None
    assert db.job_clips(job.id) == []


def test_local_time_filter_converts_naive_utc():
    from datetime import UTC, datetime

    from cortago.web.app import _local

    naive = datetime(2026, 11, 15, 2, 43)
    assert _local(naive) == naive.replace(tzinfo=UTC).astimezone().strftime("%d/%m %H:%M")


def _library(*names):
    from cortago import config

    config.MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        (config.MUSIC_DIR / name).write_bytes(b"audio")


def test_music_checkbox(client):
    r = client.post("/jobs", data={"source": "x", "music": "true"}, follow_redirects=False)
    assert db.get_job(int(r.headers["location"].rsplit("/", 1)[1])).music is True
    r = client.post("/jobs", data={"source": "y"}, follow_redirects=False)  # desmarcado = ausente
    assert db.get_job(int(r.headers["location"].rsplit("/", 1)[1])).music is False


def test_index_shows_music_library_state(client):
    assert "biblioteca vazia" in client.get("/").text
    _library("Epic_Trailer.mp3")
    r = client.get("/").text
    assert "1 faixa na biblioteca" in r
    assert 'name="music" value="true" checked' in r


def test_change_music_rerenders(client, queued, done_job):
    _library("a.mp3", "b.mp3")
    _, clip = done_job
    base = {
        "title": "Detalhe",
        "hook": "olha",
        "description": "d",
        "hashtags": "gta6",
        "start": "10",
        "end": "40",
    }
    client.post(f"/clips/{clip.id}", data={**base, "music_track": "b.mp3"})
    assert queued["renders"] == [clip.id]
    with db.session() as s:
        assert s.get(Clip, clip.id).music_track == "b.mp3"

    client.post(f"/clips/{clip.id}", data={**base, "music_track": "b.mp3"})  # sem mudança
    assert queued["renders"] == [clip.id]

    client.post(f"/clips/{clip.id}", data={**base, "music_track": "__none__"})  # sem música
    assert queued["renders"] == [clip.id, clip.id]
    with db.session() as s:
        assert s.get(Clip, clip.id).music_track == ""


def test_unknown_music_track_is_rejected(client, done_job):
    _, clip = done_job
    form = {"title": "t", "start": "10", "end": "40", "music_track": "../../cortago.db"}
    assert client.post(f"/clips/{clip.id}", data=form).status_code == 400


def test_card_shows_track_and_selector(client, done_job):
    _library("Epic_Trailer.mp3")
    _, clip = done_job
    db.update_clip(clip.id, music_track="Epic_Trailer.mp3")
    html = client.get(f"/clips/{clip.id}").text
    assert "♪ Epic Trailer" in html
    assert '<option value="Epic_Trailer.mp3" selected>' in html


def test_music_level_quick_buttons(client, queued, done_job):
    _library("a.mp3")
    _, clip = done_job
    db.update_clip(clip.id, music_track="a.mp3")

    r = client.post(f"/clips/{clip.id}/music-level", data={"delta": -25})
    assert r.status_code == 200
    with db.session() as s:
        assert s.get(Clip, clip.id).music_level == 75
    assert queued["renders"] == [clip.id]

    for _ in range(5):  # não passa de 0
        client.post(f"/clips/{clip.id}/music-level", data={"delta": -25})
    with db.session() as s:
        assert s.get(Clip, clip.id).music_level == 0
    assert len(queued["renders"]) == 4  # 75 → 50 → 25 → 0; os cliques no limite não re-renderizam


def test_music_level_requires_music(client, done_job):
    _, clip = done_job
    assert client.post(f"/clips/{clip.id}/music-level", data={"delta": 25}).status_code == 400


def test_edit_form_music_level(client, queued, done_job):
    _library("a.mp3")
    _, clip = done_job
    db.update_clip(clip.id, music_track="a.mp3")
    base = {
        "title": "Detalhe",
        "hook": "olha",
        "description": "d",
        "hashtags": "gta6",
        "start": "10",
        "end": "40",
    }

    client.post(f"/clips/{clip.id}", data={**base, "music_level": "60"})
    assert queued["renders"] == [clip.id]
    client.post(f"/clips/{clip.id}", data=base)  # sem o campo: mantém 60 e não re-renderiza
    assert queued["renders"] == [clip.id]
    with db.session() as s:
        assert s.get(Clip, clip.id).music_level == 60
    assert client.post(f"/clips/{clip.id}", data={**base, "music_level": "500"}).status_code == 422


def test_card_shows_music_level_controls(client, done_job):
    _library("a.mp3")
    _, clip = done_job
    db.update_clip(clip.id, music_track="a.mp3", music_level=125)
    html = client.get(f"/clips/{clip.id}").text
    assert "125%" in html
    assert "Música mais baixa" in html and "Música mais alta" in html
    assert 'name="music_level"' in html


def test_post_panel_shows_youtube_fields(client, done_job):
    _, clip = done_job
    html = client.get(f"/clips/{clip.id}").text
    assert "Postar no YouTube" in html
    assert f'id="yt-title-{clip.id}" readonly value="Detalhe"' in html
    assert "Créditos: Canal" in html
    assert f'id="yt-tags-{clip.id}" readonly value="gta6"' in html
    assert "Jogos" in html and "Português (Brasil)" in html
    assert "/100" in html


def test_post_panel_hidden_until_rendered_or_when_discarded(client, done_job):
    _, clip = done_job
    db.update_clip(clip.id, render_status=RenderStatus.PENDING)
    assert "Postar no YouTube" not in client.get(f"/clips/{clip.id}").text
    db.update_clip(clip.id, render_status=RenderStatus.DONE, status=ClipStatus.DISCARDED)
    assert "Postar no YouTube" not in client.get(f"/clips/{clip.id}").text


def test_post_panel_warns_about_local_file_credits(client, done_job):
    job, clip = done_job  # done_job não tem URL: veio de arquivo
    assert 'troque "Canal" nos créditos' in client.get(f"/clips/{clip.id}").text
    db.update_job(job.id, url="https://youtu.be/abc")
    assert "nos créditos pelo criador" not in client.get(f"/clips/{clip.id}").text
