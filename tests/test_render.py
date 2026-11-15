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
