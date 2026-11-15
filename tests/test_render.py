from cortago import render


def test_audio_filter_ducks_voice():
    graph = render._audio_filter(30.0, has_voice=True, volume=0.3)
    assert "sidechaincompress" in graph
    assert "volume=0.300" in graph
    assert "afade=t=out:st=28.500" in graph
    assert graph.endswith("[a]")


def test_audio_filter_without_voice_is_music_only():
    graph = render._audio_filter(10.0, has_voice=False, volume=0.3)
    assert "sidechaincompress" not in graph
    assert "[0:a]" not in graph


def test_auto_music_volume_sits_below_video():
    # música normalizada em -16 LUFS; vídeo em -15 com gap de 12 → alvo -27 LUFS → -11 dB
    assert abs(render.auto_music_volume(-15.0, gap_db=12) - 10 ** (-11 / 20)) < 1e-9


def test_auto_music_volume_is_clamped_and_scaled():
    loud = render.auto_music_volume(0.0, gap_db=12)  # vídeo absurdamente alto → limite -20 LUFS
    assert abs(loud - 10 ** (-4 / 20)) < 1e-9
    quiet = render.auto_music_volume(-60.0, gap_db=12)  # muito baixo → limite -40 LUFS
    assert abs(quiet - 10 ** (-24 / 20)) < 1e-9
    assert render.auto_music_volume(-15.0, gap_db=12, level=0) == 0
    assert (
        abs(render.auto_music_volume(-15.0, 12, level=150) / render.auto_music_volume(-15.0, 12) - 1.5) < 1e-9
    )


def test_auto_music_volume_without_voice():
    assert abs(render.auto_music_volume(None) - 10 ** (-4 / 20)) < 1e-9


def test_parse_integrated_loudness():
    log = """[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:         -15.2 LUFS
    Threshold: -25.6 LUFS
"""
    assert render.parse_integrated_loudness(log) == -15.2
    assert render.parse_integrated_loudness("    I:         -70.0 LUFS") is None
    assert render.parse_integrated_loudness("    I:          -inf LUFS") is None
    assert render.parse_integrated_loudness("sem resumo") is None
