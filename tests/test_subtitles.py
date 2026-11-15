from cortago.subtitles import _chunks, _ts, ass_color, write_ass
from cortago.transcribe import Word


def w(text: str, start: float, end: float) -> Word:
    return Word(text=text, start=start, end=end)


def test_ts_format():
    assert _ts(0) == "0:00:00.00"
    assert _ts(65.5) == "0:01:05.50"
    assert _ts(3725.25) == "1:02:05.25"
    assert _ts(-1) == "0:00:00.00"


def test_chunks_limit_words():
    words = [w(str(i), i * 0.3, i * 0.3 + 0.25) for i in range(7)]
    assert [len(c) for c in _chunks(words)] == [3, 3, 1]


def test_chunks_break_on_pause_and_sentence_end():
    words = [w("oi", 0, 0.2), w("galera.", 0.3, 0.6), w("hoje", 0.7, 0.9), w("tem", 2.0, 2.2)]
    assert [[x.text for x in c] for c in _chunks(words)] == [["oi", "galera."], ["hoje"], ["tem"]]


def test_write_ass_shifts_times_and_highlights(tmp_path):
    words = [w("antes", 1.0, 1.5), w("olha", 10.0, 10.4), w("isso", 10.5, 10.9)]
    out = tmp_path / "c.ass"
    write_ass(words, clip_start=10.0, clip_end=11.0, hook="gancho {x}", out=out)
    text = out.read_text()

    assert "ANTES" not in text  # fora do corte
    assert "Hook,,0,0,0,,GANCHO X" in text  # chaves removidas, sem quebrar o ASS
    dialogues = [line for line in text.splitlines() if line.startswith("Dialogue: 0")]
    assert len(dialogues) == 2
    assert dialogues[0].startswith("Dialogue: 0,0:00:00.00,0:00:00.50,")
    assert r"{\c&H00953CE3&}OLHA" in dialogues[0]  # magenta da marca, #E33C95 em BGR
    assert r"{\c&H00953CE3&}ISSO" in dialogues[1]
    assert "&H00540830,&H00540830" in text  # caixa do gancho em #300854


def test_ass_color_converts_rgb_to_bgr():
    assert ass_color("#E33C95") == "&H00953CE3"
    assert ass_color("FFD400", alpha=0x80) == "&H8000D4FF"
