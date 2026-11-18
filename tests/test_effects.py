import pytest

from cortago import config, effects, render
from cortago.transcribe import Word


def words(*spans):
    return [Word(text=f"p{i}", start=a, end=b) for i, (a, b) in enumerate(spans)]


def test_no_words_keeps_whole_clip():
    assert effects.speech_segments([], 10, 20) == [(10, 20)]


def test_leading_silence_and_long_pause_are_removed():
    ws = words((11.0, 11.5), (11.6, 12.0), (14.0, 14.5))  # pausa de 2 s entre 12,0 e 14,0
    segs = effects.speech_segments(ws, 10.0, 15.0)
    assert segs[0][0] == pytest.approx(11.0 - effects.PAD)  # começa já na primeira palavra
    assert segs[0][1] == pytest.approx(12.0 + effects.PAD)
    assert segs[1][0] == pytest.approx(14.0 - effects.PAD)
    assert segs[-1][1] == pytest.approx(14.5 + effects.TAIL)


def test_short_pauses_are_kept():
    ws = words((10.0, 10.5), (10.7, 11.0))  # 0,2 s < MAX_PAUSE
    assert effects.speech_segments(ws, 10.0, 11.0) == [(10.0, 11.0)]


def test_pause_with_sound_is_kept():
    ws = words((10.0, 10.5), (13.0, 13.5))  # 2,5 s sem fala…
    quiet = [(11.8, 12.4)]  # …mas só 0,6 s é silêncio de verdade (o resto é som do jogo)
    segs = effects.speech_segments(ws, 10.0, 13.5, quiet)
    removed = 3.5 - effects.total_duration(segs)
    assert removed == pytest.approx(0.6 - 2 * effects.PAD)


def test_pause_without_any_silence_is_kept():
    ws = words((10.0, 10.5), (13.0, 13.5))
    assert effects.speech_segments(ws, 10.0, 13.5, quiet=[]) == [(10.0, 13.5)]


def test_remap_skips_removed_pauses():
    segs = [(10.0, 12.0), (14.0, 15.0)]
    assert effects.remap(10.5, segs) == pytest.approx(0.5)
    assert effects.remap(14.5, segs) == pytest.approx(2.5)
    assert effects.remap(13.0, segs) == pytest.approx(2.0)  # dentro da pausa → começo do trecho seguinte
    assert effects.remap(20.0, segs) == pytest.approx(3.0)


def test_parse_silences():
    log = (
        "[silencedetect @ 0x1] silence_start: 1.5\n"
        "[silencedetect @ 0x1] silence_end: 2.4 | silence_duration: 0.9\n"
        "[silencedetect @ 0x1] silence_start: 7.0\n"
    )
    assert effects.parse_silences(log, offset=100) == [(101.5, 102.4), (107.0, float("inf"))]


def test_quiet_threshold_is_relative_and_clamped():
    assert effects.quiet_threshold_db(-15) == -35
    assert effects.quiet_threshold_db(-5) == -30
    assert effects.quiet_threshold_db(-50) == -55
    assert effects.quiet_threshold_db(None) == -40


def test_invalid_effect_values():
    with pytest.raises(ValueError):
        effects.Effects(intro_zoom="gigante")
    with pytest.raises(ValueError):
        effects.Effects(hook_sfx="buzina")


def test_defaults_ignore_invalid_env(monkeypatch):
    monkeypatch.setattr(config, "FX_INTRO_ZOOM", "gigante")
    monkeypatch.setattr(config, "FX_HOOK_SFX", "buzina")
    d = effects.defaults()
    assert (d["intro_zoom"], d["hook_sfx"]) == ("none", "none")


def test_hook_override():
    assert effects.hook_override(False) == ""
    assert r"\t(0,220,\fscx100\fscy100)" in effects.hook_override(True)


def test_zoom_expression_returns_to_normal():
    expr = effects.zoom_scale_expr(0.1, 1080)
    assert expr.startswith("trunc(1080*(1+0.1*pow(max(0,1-t/0.6),2))")


def test_source_filter_concatenates_segments():
    parts, v, a = render._source_filter([(0.0, 2.0), (3.0, 4.5)], has_voice=True)
    graph = ";".join(parts)
    assert "split=2" in graph and "asplit=2" in graph
    assert "trim=3.000:4.500" in graph
    assert "concat=n=2:v=1:a=1[vsrc][asrc]" in graph
    assert (v, a) == ("[vsrc]", "[asrc]")


def test_source_filter_without_audio():
    parts, v, a = render._source_filter([(0.0, 2.0), (3.0, 4.5)], has_voice=False)
    assert "concat=n=2:v=1:a=0[vsrc]" in ";".join(parts)
    assert a is None
