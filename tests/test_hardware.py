from types import SimpleNamespace

import pytest

from cortago import config, hardware, transcribe


@pytest.fixture(autouse=True)
def clear_caches(monkeypatch):
    monkeypatch.setattr(config, "WHISPER_BACKEND", "")
    monkeypatch.setattr(config, "WHISPER_MODEL", "")
    monkeypatch.setattr(config, "VIDEO_ENCODER", "")
    hardware.whisper_setup.cache_clear()
    hardware.video_encoder.cache_clear()
    yield
    hardware.whisper_setup.cache_clear()
    hardware.video_encoder.cache_clear()


def fake_machine(monkeypatch, system, machine="x86_64", cuda=0):
    monkeypatch.setattr(hardware.platform, "system", lambda: system)
    monkeypatch.setattr(hardware.platform, "machine", lambda: machine)
    monkeypatch.setattr(hardware, "cuda_devices", lambda: cuda)


def test_apple_silicon_uses_mlx(monkeypatch):
    fake_machine(monkeypatch, "Darwin", "arm64")
    setup = hardware.whisper_setup()
    assert (setup.backend, setup.device) == ("mlx", "apple-gpu")
    assert setup.model == "mlx-community/whisper-large-v3-turbo"


def test_windows_with_nvidia_uses_cuda(monkeypatch):
    fake_machine(monkeypatch, "Windows", cuda=1)
    setup = hardware.whisper_setup()
    assert (setup.backend, setup.device, setup.compute_type) == ("faster-whisper", "cuda", "float16")
    assert setup.model == "large-v3-turbo"


@pytest.mark.parametrize("system", ["Windows", "Linux", "Darwin"])
def test_without_gpu_uses_cpu_int8(monkeypatch, system):
    fake_machine(monkeypatch, system, "x86_64")  # inclui Mac Intel
    setup = hardware.whisper_setup()
    assert (setup.backend, setup.device, setup.compute_type) == ("faster-whisper", "cpu", "int8")


def test_env_overrides_backend_and_model(monkeypatch):
    fake_machine(monkeypatch, "Darwin", "arm64")
    monkeypatch.setattr(config, "WHISPER_BACKEND", "faster-whisper")
    monkeypatch.setattr(config, "WHISPER_MODEL", "small")
    setup = hardware.whisper_setup()
    assert (setup.backend, setup.model) == ("faster-whisper", "small")


def test_invalid_backend(monkeypatch):
    monkeypatch.setattr(config, "WHISPER_BACKEND", "openai")
    with pytest.raises(ValueError):
        hardware.whisper_setup()


@pytest.mark.parametrize(
    ("system", "working", "expected"),
    [
        ("Darwin", {"h264_videotoolbox"}, "h264_videotoolbox"),
        ("Windows", {"h264_nvenc", "h264_qsv"}, "h264_nvenc"),
        ("Windows", {"h264_amf"}, "h264_amf"),
        ("Linux", {"h264_qsv"}, "h264_qsv"),
        ("Windows", set(), "libx264"),
        ("Darwin", set(), "libx264"),
    ],
)
def test_encoder_picks_first_that_works(monkeypatch, system, working, expected):
    fake_machine(monkeypatch, system)
    monkeypatch.setattr(hardware, "_encoder_works", lambda enc: enc in working)
    assert hardware.video_encoder() == expected


def test_encoder_env_override_skips_detection(monkeypatch):
    monkeypatch.setattr(config, "VIDEO_ENCODER", "libx264")
    monkeypatch.setattr(hardware, "_encoder_works", lambda enc: pytest.fail("não deveria testar"))
    assert hardware.video_encoder() == "libx264"


def test_encoder_args():
    assert hardware.encoder_args("libx264")[:2] == ["-c:v", "libx264"]
    assert "-crf" in hardware.encoder_args("libx264")
    assert hardware.encoder_args("h264_nvenc") == ["-c:v", "h264_nvenc", "-b:v", config.VIDEO_BITRATE]


def test_faster_whisper_segments_are_mapped():
    words = [SimpleNamespace(word=" Olha", start=0.0, end=0.3), SimpleNamespace(word=" ", start=0.3, end=0.3)]
    segs = [SimpleNamespace(start=0.0, end=0.5, text=" Olha isso ", words=words)]
    tr = transcribe.segments_from_faster_whisper(iter(segs), "pt")
    assert tr.language == "pt"
    assert tr.segments[0].text == "Olha isso"
    assert [(w.text, w.start, w.end) for w in tr.words] == [("Olha", 0.0, 0.3)]
