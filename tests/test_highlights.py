from cortago.highlights import Clip, _snap_to_words
from cortago.transcribe import Segment, Transcript, Word


def make_transcript() -> Transcript:
    words = [Word(text=f"p{i}", start=i * 1.0, end=i * 1.0 + 0.8) for i in range(30)]
    return Transcript(language="pt", segments=[Segment(start=0, end=30, text="", words=words)])


def clip(start: float, end: float) -> Clip:
    return Clip(start=start, end=end, title="t", hook="h", description="d", hashtags=[], score=5, reason="r")


def test_snap_expands_to_word_boundaries():
    snapped = _snap_to_words(clip(5.3, 10.2), make_transcript(), pad=0.1)
    assert snapped.start == 4.9  # palavra p5 começa em 5.0
    assert snapped.end == 10.9  # palavra p10 termina em 10.8


def test_snap_never_negative():
    assert _snap_to_words(clip(0.0, 3.0), make_transcript(), pad=0.5).start == 0.0


def test_snap_without_words_keeps_clip():
    original = clip(100.0, 120.0)
    assert _snap_to_words(original, make_transcript()) == original
