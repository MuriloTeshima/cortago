from cortago import config, post_info
from cortago.db import Clip, Job


def make(hashtags=None, title="Detalhe escondido no trailer", music_track=None):
    job = Job(id=1, source="x", channel="Canal Original", url="https://youtu.be/abc")
    clip = Clip(
        id=1,
        job_id=1,
        position=1,
        start=0,
        end=30,
        title=title,
        hook="h",
        description="Um detalhe que ninguém viu.",
        hashtags=hashtags if hashtags is not None else ["GTA6", "#Rockstar"],
        score=8,
        reason="r",
        music_track=music_track,
    )
    return clip, job


def test_description_has_credits_and_hashtags():
    clip, job = make()
    info = post_info.build(clip, job)
    assert info.description == (
        "Um detalhe que ninguém viu.\n\nCréditos: Canal Original — https://youtu.be/abc\n\n#GTA6 #Rockstar"
    )
    assert info.title == "Detalhe escondido no trailer"


def test_tags_dedupe_and_extra(monkeypatch):
    monkeypatch.setattr(config, "YT_EXTRA_TAGS", "games, gta6 ,cortes de games,")
    clip, job = make()
    assert post_info.build(clip, job).tags == "GTA6, Rockstar, games, cortes de games"


def test_tags_respect_youtube_limit():
    clip, job = make(hashtags=[f"tag numero {i}" for i in range(100)])
    tags = post_info.build(clip, job).tags.split(", ")
    assert post_info.tags_length(tags) <= post_info.TAGS_LIMIT
    assert len(tags) < 100


def test_tags_length_counts_quotes_and_commas():
    assert post_info.tags_length(["gta6", "cortes de games"]) == 4 + (15 + 2) + 1


def test_title_over_limit_is_flagged():
    clip, job = make(title="x" * 101)
    assert post_info.build(clip, job).title_over


def test_music_credit_in_description(monkeypatch):
    config.MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    (config.MUSIC_DIR / "a.mp3").write_bytes(b"x")
    (config.MUSIC_DIR / "a.txt").write_text("Faixa X por Fulano")
    clip, job = make(music_track="a.mp3")
    assert "Música: Faixa X por Fulano" in post_info.build(clip, job).description


def test_manual_fields_from_config(monkeypatch):
    monkeypatch.setattr(config, "YT_CATEGORY", "Entretenimento")
    clip, job = make()
    assert post_info.build(clip, job).category == "Entretenimento"
