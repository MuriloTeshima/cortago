from cortago import config, music


def setup_library(*names):
    config.MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        (config.MUSIC_DIR / name).write_bytes(b"audio")


def test_tracks_lists_only_audio_sorted():
    setup_library("b.mp3", "a.m4a", "notas.txt", "capa.jpg")
    assert music.tracks() == ["a.m4a", "b.mp3"]


def test_path_rejects_traversal_and_missing():
    setup_library("a.mp3")
    assert music.path("a.mp3") == config.MUSIC_DIR / "a.mp3"
    assert music.path("../cortago.db") is None
    assert music.path("nao-existe.mp3") is None
    assert music.path("") is None


def test_pick_is_deterministic_and_handles_empty():
    assert music.pick(1) is None
    setup_library("a.mp3", "b.mp3", "c.mp3")
    assert music.pick(42) == music.pick(42)
    assert {music.pick(i) for i in range(50)} == {"a.mp3", "b.mp3", "c.mp3"}


def test_offset_stays_inside_track():
    for seed in range(20):
        off = music.offset(track_duration=180, clip_duration=40, seed=seed)
        assert 0 <= off <= 180 - 40 - 5
    assert music.offset(track_duration=45, clip_duration=40, seed=1) == 0.0


def test_credit_from_sidecar_txt():
    setup_library("a.mp3", "b.mp3")
    (config.MUSIC_DIR / "a.txt").write_text("  Artista - Faixa  \n", encoding="utf-8")
    assert music.credit("a.mp3") == "Artista - Faixa"
    assert music.credit("b.mp3") is None


def test_credit_ignores_windows_bom():
    setup_library("a.mp3")
    (config.MUSIC_DIR / "a.txt").write_bytes("﻿Música por Fulano".encode())
    assert music.credit("a.mp3") == "Música por Fulano"
