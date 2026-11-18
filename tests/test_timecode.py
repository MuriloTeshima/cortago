import pytest

from cortago import timecode


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("1:20:00", 4800),
        ("80:00", 4800),
        ("4800", 4800),
        ("4800,5", 4800.5),
        ("1h20m", 4800),
        ("1h20m30s", 4830),
        ("90s", 90),
        ("2m", 120),
        (" 0:45 ", 45),
    ],
)
def test_parse(text, seconds):
    assert timecode.parse(text) == pytest.approx(seconds)


@pytest.mark.parametrize("text", [None, "", "   "])
def test_parse_empty(text):
    assert timecode.parse(text) is None


@pytest.mark.parametrize("text", ["abc", "1:2:3:4", "1:aa", "h", "1x"])
def test_parse_invalid(text):
    with pytest.raises(ValueError):
        timecode.parse(text)


def test_format():
    assert timecode.format(4830) == "1:20:30"
    assert timecode.format(245) == "4:05"
    assert timecode.format(None) == "—"


def test_link_at_instant():
    assert (
        timecode.at("https://www.youtube.com/watch?v=abc", 4830.7)
        == "https://www.youtube.com/watch?v=abc&t=4830s"
    )
    assert timecode.at("https://youtu.be/abc?t=10", 65) == "https://youtu.be/abc?t=65s"
    assert (
        timecode.at("https://www.twitch.tv/videos/123", 4830) == "https://www.twitch.tv/videos/123?t=1h20m30s"
    )
    assert timecode.at("https://kick.com/video/x", 30) == "https://kick.com/video/x"
    assert timecode.at("", 30) == ""
