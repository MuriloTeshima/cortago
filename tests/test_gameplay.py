import pytest

from cortago import config, gameplay, highlights, render
from cortago.transcribe import Word


def sentence_words():
    """Frases de ~2,4s com ponto final: 'a b c.' começando a cada 2,5s, de 10s a 40s."""
    words = []
    t = 10.0
    while t < 39:
        for i, text in enumerate(["um", "dois", "tres."]):
            words.append(Word(text=text, start=t + i * 0.8, end=t + i * 0.8 + 0.6))
        t += 2.5
    return words


def test_blocks_cover_clip_and_respect_limits():
    bl = gameplay.blocks(sentence_words(), 10, 40)
    assert bl[0][0] == 10 and bl[-1][1] == 40
    assert all(b == c for (_, b), (c, _) in zip(bl, bl[1:], strict=False))  # sem buracos
    assert all(gameplay.MIN_BLOCK <= b - a <= gameplay.MAX_BLOCK + 1 for a, b in bl)


def test_blocks_split_long_speech_without_punctuation():
    words = [Word(text=f"p{i}", start=i * 0.5, end=i * 0.5 + 0.4) for i in range(60)]
    bl = gameplay.blocks(words, 0, 30)
    assert len(bl) >= 4
    assert all(b - a <= gameplay.MAX_BLOCK + 0.5 for a, b in bl)


def test_short_clip_or_no_words_is_one_block():
    assert gameplay.blocks([], 0, 30) == [(0, 30)]
    assert gameplay.blocks(sentence_words(), 10, 11.5) == [(10, 11.5)]


def test_plan_alternates_and_keeps_hook_on_speaker():
    spans = gameplay.plan(sentence_words(), 10, 40)
    assert spans and spans[0][0] >= 10 + gameplay.HOOK_SECONDS  # o gancho fica em quem fala
    bl = gameplay.blocks(sentence_words(), 10, 40)
    flags = gameplay.choose(bl, None, 10)
    first = flags.index(True)
    assert not any(flags[:first]) and bl[first][0] >= 10 + gameplay.HOOK_SECONDS
    # Depois do gancho, alterna bloco a bloco.
    assert all(flags[i] != flags[i + 1] for i in range(first, len(flags) - 1))


def test_plan_follows_claude_hints():
    words = sentence_words()
    bl = gameplay.blocks(words, 10, 40)
    target = bl[3]
    spans = gameplay.plan(words, 10, 40, hints=[target])
    assert spans == [target]
    # Indicação dentro do gancho é ignorada.
    assert gameplay.plan(words, 10, 40, hints=[(10, 12)]) == []


def test_effective_spans_priority():
    class C:
        start, end = 10.0, 40.0
        gameplay_mode = "alternar"
        gameplay_hints = None
        edit = None

    c = C()
    assert gameplay.effective_spans(c, sentence_words()) == gameplay.plan(sentence_words(), 10, 40)
    c.gameplay_hints = [[20, 25]]
    assert gameplay.effective_spans(c, sentence_words()) == gameplay.plan(
        sentence_words(), 10, 40, [(20, 25)]
    )
    c.edit = {"gameplay": [[30, 35]]}
    assert gameplay.effective_spans(c, sentence_words()) == [(30.0, 35.0)]
    c.edit = {"gameplay": []}  # ajuste manual "nenhuma gameplay" vale
    assert gameplay.effective_spans(c, sentence_words()) == []
    c.gameplay_mode = "dividida"
    assert gameplay.effective_spans(c, sentence_words()) == [(10.0, 40.0)]
    c.gameplay_mode = "none"
    assert gameplay.effective_spans(c, sentence_words()) == []


def test_validate_spans_clamps_merges_and_rejects():
    assert gameplay.validate_spans([(5, 12), (12, 15), (38, 50)], 10, 40) == [(10, 15), (38, 40)]
    with pytest.raises(ValueError):
        gameplay.validate_spans([(20, 18)], 10, 40)


def test_to_output_follows_jump_cuts():
    # Corte 10–40 sem a parte 20–25: o que vem depois de 25 anda 5s para trás.
    segs = [(10, 20), (25, 40)]
    assert gameplay.to_output([(12, 18), (26, 30)], 10, segs) == [(2.0, 8.0), (11.0, 15.0)]
    # Bloco que cai inteiro na parte removida some.
    assert gameplay.to_output([(21, 24)], 10, segs) == []
    assert gameplay.to_output([(12, 18)], 10, None) == [(2.0, 8.0)]


def test_enable_expr():
    assert gameplay.enable_expr([(1, 2), (3.5, 4)]) == "between(t,1.000,2.000)+between(t,3.500,4.000)"
    assert gameplay.enable_expr([]) == "0"


def test_render_filters_for_both_modes():
    bg = render.Gameplay(path=config.ROOT / "x.mp4", mode="alternar", spans=[(3, 6)])
    f = render._gameplay_filter(bg, "[1:v]", "[vsrc]", "blur", 30, "[vl]")
    assert "overlay=0:0:enable='between(t,3.000,6.000)'" in f and "trim=duration=30.000" in f
    assert "boxblur" in f  # quem fala continua no layout escolhido

    split = render._gameplay_filter(
        render.Gameplay(path=config.ROOT / "x.mp4", mode="dividida"), "[1:v]", "[vsrc]", "blur", 30, "[vl]"
    )
    assert "vstack=inputs=2[vl]" in split and f"crop={config.OUT_W}:{config.OUT_H // 2}" in split


def test_prompt_and_schema_only_ask_for_gameplay_when_needed():
    assert "gameplay" not in highlights.system_prompt(20, 60)
    assert "gameplay de fundo" in highlights.system_prompt(20, 60, gameplay=True)
    assert "gameplay" not in highlights.schema()["properties"]["clips"]["items"]["properties"]
    item = highlights.schema(True)["properties"]["clips"]["items"]
    assert "gameplay" in item["properties"] and "gameplay" in item["required"]
    assert (
        "gameplay" not in highlights.SCHEMA["properties"]["clips"]["items"]["properties"]
    )  # não altera o original


def test_parse_clips_reads_gameplay_spans():
    text = (
        '{"clips": [{"start": 1, "end": 30, "title": "t", "hook": "h", "description": "d", "hashtags": [],'
        ' "score": 5, "reason": "r", "gameplay": [{"start": 5, "end": 9}, {"start": 12, "end": 11}]}]}'
    )
    (clip,) = highlights.parse_clips(text)
    assert clip.gameplay == [(5.0, 9.0)]
