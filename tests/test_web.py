from pathlib import Path

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


def test_local_time_filter_converts_naive_utc():
    from datetime import UTC, datetime

    from cortago.web.common import _local

    naive = datetime(2026, 11, 15, 2, 43)
    assert _local(naive) == naive.replace(tzinfo=UTC).astimezone().strftime("%d/%m %H:%M")


# ---------- galeria ----------


def test_job_page_is_a_gallery(client, done_job):
    job, clip = done_job
    html = client.get(f"/jobs/{job.id}").text
    assert f'href="/clips/{clip.id}"' in html  # cada miniatura abre o editor
    assert f"/media/{job.id}/{clip.id}.jpg?v=1" in html
    assert "Detalhe" in html
    assert "hx-trigger" not in html  # nada rodando, então sem polling


def test_tile_polls_while_rendering(client, done_job):
    _, clip = done_job
    db.update_clip(clip.id, render_status=RenderStatus.RENDERING)
    html = client.get(f"/clips/{clip.id}/tile").text
    assert f'hx-get="/clips/{clip.id}/tile"' in html and "Renderizando" in html


def test_thumbnail_is_generated_on_demand(client, done_job, monkeypatch):
    from cortago.web.routes import media

    job, clip = done_job
    video = pipeline.clip_path(job, clip)
    video.parent.mkdir(parents=True)
    video.write_bytes(b"mp4")
    made = []
    monkeypatch.setattr(media.render, "thumbnail", lambda v, out: (made.append(v), out.write_bytes(b"jpg")))
    assert client.get(f"/media/{job.id}/{clip.id}.jpg").content == b"jpg"
    client.get(f"/media/{job.id}/{clip.id}.jpg")
    assert len(made) == 1  # depois da primeira vez, reaproveita


# ---------- editor ----------


def test_editor_page(client, done_job):
    job, clip = done_job
    html = client.get(f"/clips/{clip.id}").text
    for tab in ("texto", "corte", "audio", "efeitos", "postar"):
        assert f'data-tab="{tab}"' in html and f'id="sec-{tab}"' in html
    assert f'src="/media/{job.id}/{clip.id}.mp4?v=1"' in html
    assert "Corte 1 de 1" in html
    assert f'href="/jobs/{job.id}"' in html


def test_editor_navigation_between_clips(client, done_job):
    job, clip = done_job
    with db.session() as s:
        other = Clip(
            job_id=job.id,
            position=2,
            start=50,
            end=80,
            title="Outro",
            hook="",
            description="",
            hashtags=[],
            score=6,
            reason="",
        )
        s.add(other)
        s.commit()
        s.refresh(other)
    first = client.get(f"/clips/{clip.id}").text
    assert f'href="/clips/{other.id}"' in first and "Próximo" in first and "Anterior" not in first
    second = client.get(f"/clips/{other.id}").text
    assert f'href="/clips/{clip.id}"' in second and "Anterior" in second and "Próximo" not in second


def test_missing_clip_is_404(client):
    assert client.get("/clips/999").status_code == 404


def test_save_text_updates_section_player_and_post_panel(client, queued, done_job):
    _, clip = done_job
    form = {"title": "Novo título", "hook": "olha", "description": "nova", "hashtags": "#gta6 #rockstar"}
    html = client.post(f"/clips/{clip.id}/texto", data=form).text
    assert queued["renders"] == []  # gancho igual: sem render
    assert 'id="sec-texto"' in html and "✓ Salvo" in html
    assert 'id="player"' in html and 'hx-swap-oob="true"' in html  # player atualizado fora da área alvo
    assert f'id="yt-title-{clip.id}" readonly value="Novo título"' in html  # painel de postagem também
    with db.session() as s:
        assert s.get(Clip, clip.id).hashtags == ["gta6", "rockstar"]


def test_save_text_with_new_hook_rerenders(client, queued, done_job):
    _, clip = done_job
    client.post(f"/clips/{clip.id}/texto", data={"title": "t", "hook": "outro gancho"})
    assert queued["renders"] == [clip.id]


def test_save_text_requires_title(client, done_job):
    _, clip = done_job
    assert client.post(f"/clips/{clip.id}/texto", data={"title": " ", "hook": "olha"}).status_code == 400


def test_save_cut(client, queued, done_job):
    _, clip = done_job
    client.post(f"/clips/{clip.id}/corte", data={"start": "12", "end": "38"})
    assert queued["renders"] == [clip.id]
    assert client.post(f"/clips/{clip.id}/corte", data={"start": "40", "end": "10"}).status_code == 400


def test_cut_shown_in_original_video_time(client, done_job):
    job, clip = done_job
    db.update_job(job.id, source_offset=4800, range_start=4800, range_end=7200)
    assert "trecho 1:20:00–2:00:00" in client.get(f"/jobs/{job.id}").text
    html = client.get(f"/clips/{clip.id}").text
    assert "1:20:10–1:20:40" in html
    assert 'name="start" value="4810.0"' in html


def test_save_audio(client, queued, done_job):
    _library("a.mp3", "b.mp3")
    _, clip = done_job
    client.post(f"/clips/{clip.id}/audio", data={"music_track": "b.mp3", "music_level": "80"})
    with db.session() as s:
        c = s.get(Clip, clip.id)
    assert (c.music_track, c.music_level) == ("b.mp3", 80)
    client.post(f"/clips/{clip.id}/audio", data={"music_track": "__none__", "music_level": "80"})
    with db.session() as s:
        assert s.get(Clip, clip.id).music_track == ""
    assert queued["renders"] == [clip.id, clip.id]
    assert client.post(f"/clips/{clip.id}/audio", data={"music_track": "../x"}).status_code == 400
    assert client.post(f"/clips/{clip.id}/audio", data={"music_level": "500"}).status_code == 422


def test_audio_quick_buttons(client, queued, done_job):
    _library("a.mp3")
    _, clip = done_job
    assert client.post(f"/clips/{clip.id}/audio/nivel", data={"delta": 25}).status_code == 400  # sem música
    db.update_clip(clip.id, music_track="a.mp3")
    html = client.post(f"/clips/{clip.id}/audio/nivel", data={"delta": -25}).text
    assert "Música mais baixa" in html and "♪ a · 75%" in html
    assert queued["renders"] == [clip.id]


def test_audio_section_has_preview(client, done_job):
    _library("a b.mp3")
    _, clip = done_job
    db.update_clip(clip.id, music_track="a b.mp3")
    html = client.get(f"/clips/{clip.id}").text
    assert f'data-music-preview="#preview-{clip.id}"' in html
    assert 'src="/music/a%20b.mp3"' in html
    assert '<option value="a b.mp3" selected>' in html


def test_save_effects(client, queued, done_job):
    _, clip = done_job
    client.post(
        f"/clips/{clip.id}/efeitos", data={"jump_cuts": "true", "intro_zoom": "forte", "hook_sfx": "pop"}
    )
    with db.session() as s:
        c = s.get(Clip, clip.id)
    assert (c.jump_cuts, c.intro_zoom, c.hook_sfx, c.hook_anim, c.progress_bar) == (
        True,
        "forte",
        "pop",
        False,
        False,
    )
    assert queued["renders"] == [clip.id]
    client.post(f"/clips/{clip.id}/efeitos", data={})  # tudo desmarcado
    with db.session() as s:
        c = s.get(Clip, clip.id)
    assert (c.jump_cuts, c.intro_zoom, c.hook_sfx) == (False, "none", "none")
    assert client.post(f"/clips/{clip.id}/efeitos", data={"hook_sfx": "buzina"}).status_code == 400


def test_effects_summary_in_player(client, done_job):
    _, clip = done_job
    db.update_clip(clip.id, jump_cuts=True, intro_zoom="suave", hook_sfx="whoosh")
    html = client.get(f"/clips/{clip.id}").text
    assert "✦ sem silêncios · zoom suave · som whoosh" in html
    assert '<option value="whoosh" selected>Whoosh</option>' in html


def test_status_buttons_return_player(client, queued, done_job):
    _, clip = done_job
    html = client.post(f"/clips/{clip.id}/status", data={"status": "approved"}).text
    assert 'id="player"' in html and "Aprovado" in html
    client.post(f"/clips/{clip.id}/status", data={"status": "discarded"})
    with db.session() as s:
        assert s.get(Clip, clip.id).status == ClipStatus.DISCARDED


def test_rerender_button(client, queued, done_job):
    _, clip = done_job
    assert 'id="player"' in client.post(f"/clips/{clip.id}/render").text
    assert queued["renders"] == [clip.id]


def test_player_polls_while_rendering(client, done_job):
    _, clip = done_job
    db.update_clip(clip.id, render_status=RenderStatus.PENDING)
    html = client.get(f"/clips/{clip.id}/player").text
    assert f'hx-get="/clips/{clip.id}/player"' in html and "Na fila" in html


# ---------- postar ----------


def test_post_panel_shows_youtube_fields(client, done_job):
    _, clip = done_job
    html = client.get(f"/clips/{clip.id}").text
    assert f'id="yt-title-{clip.id}" readonly value="Detalhe"' in html
    assert "Créditos: Canal" in html
    assert f'id="yt-tags-{clip.id}" readonly value="gta6"' in html
    assert "Jogos" in html and "Português (Brasil)" in html


def test_post_panel_waits_for_render_and_hides_when_discarded(client, done_job):
    _, clip = done_job
    db.update_clip(clip.id, render_status=RenderStatus.PENDING)
    assert "aguarde o render terminar" in client.get(f"/clips/{clip.id}").text
    db.update_clip(clip.id, render_status=RenderStatus.DONE, status=ClipStatus.DISCARDED)
    assert "Restaure para postar" in client.get(f"/clips/{clip.id}").text


def test_post_panel_warns_about_local_file_credits(client, done_job):
    job, clip = done_job  # done_job não tem URL: veio de arquivo
    assert 'troque "Canal" nos créditos' in client.get(f"/clips/{clip.id}").text
    db.update_job(job.id, url="https://youtu.be/abc")
    assert "nos créditos pelo criador" not in client.get(f"/clips/{clip.id}").text


def test_sfx_preview(client, monkeypatch):
    from cortago.web.routes import library

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"RIFFfake")

    monkeypatch.setattr(library.subprocess, "run", fake_run)
    r = client.get("/sfx/pop.wav")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert client.get("/sfx/none.wav").status_code == 404
    assert client.get("/sfx/buzina.wav").status_code == 404


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


def test_music_preview_endpoint(client):
    _library("Epic Trailer.mp3")
    r = client.get("/music/Epic%20Trailer.mp3")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"audio"
    assert client.get("/music/nao-existe.mp3").status_code == 404
    assert client.get("/music/..%2Fcortago.db").status_code == 404


def test_music_library_page(client):
    from cortago import config

    _library("trap_Beat.mp3")
    (config.MUSIC_DIR / "trap_Beat.txt").write_text("Beat por Fulano", encoding="utf-8")
    html = client.get("/musicas").text
    assert "trap Beat" in html
    assert 'src="/music/trap_Beat.mp3"' in html
    assert "crédito: Beat por Fulano" in html
    assert '<a href="/musicas">1 faixa na biblioteca</a>' in client.get("/").text


def test_brand_assets_are_served(client):
    html = client.get("/").text
    assert 'href="/static/brand/favicon.ico"' in html
    assert 'src="/static/brand/logo.png" alt="CortaGo"' in html
    for path in ("favicon.ico", "icon-32.png", "apple-touch-icon.png", "logo.png"):
        assert client.get(f"/static/brand/{path}").status_code == 200


def test_create_job_with_range(client):
    r = client.post(
        "/jobs", data={"source": "x", "range_start": "1:20:00", "range_end": "2h"}, follow_redirects=False
    )
    job = db.get_job(int(r.headers["location"].rsplit("/", 1)[1]))
    assert (job.range_start, job.range_end) == (4800, 7200)


def test_create_job_with_invalid_range(client):
    assert client.post("/jobs", data={"source": "x", "range_start": "abc"}).status_code == 400
    assert (
        client.post("/jobs", data={"source": "x", "range_start": "1:00", "range_end": "1:10"}).status_code
        == 400
    )
