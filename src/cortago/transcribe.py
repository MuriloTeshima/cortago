"""Transcrição local com timestamps por palavra (mlx-whisper, roda na GPU do M4)."""

import functools
import logging
import subprocess
from pathlib import Path

from pydantic import BaseModel

from cortago import hardware

log = logging.getLogger("cortago.transcribe")


class Word(BaseModel):
    text: str
    start: float
    end: float


class Segment(BaseModel):
    start: float
    end: float
    text: str
    words: list[Word]


class Transcript(BaseModel):
    language: str
    segments: list[Segment]

    @property
    def words(self) -> list[Word]:
        return [w for s in self.segments for w in s.words]


def transcribe(
    video: Path, cache: Path, language: str | None = None, window: tuple[float, float | None] | None = None
) -> Transcript:
    """Transcreve o vídeo, ou só `window` (início, fim em segundos do arquivo). Os tempos saem em segundos do arquivo."""
    if cache.exists():
        return Transcript.model_validate_json(cache.read_text(encoding="utf-8"))

    start, end = window or (0.0, None)
    audio = load_audio(video, start, end)
    setup = hardware.whisper_setup()
    if setup.backend == "mlx":
        transcript = _transcribe_mlx(audio, setup, language)
    else:
        transcript = _transcribe_faster_whisper(audio, setup, language)
    transcript = shift(transcript, start)
    cache.write_text(transcript.model_dump_json(indent=1), encoding="utf-8")
    return transcript


def shift(transcript: Transcript, seconds: float) -> Transcript:
    """Soma `seconds` a todos os tempos (o áudio do trecho começa em 0, o arquivo não)."""
    if not seconds:
        return transcript
    return Transcript(
        language=transcript.language,
        segments=[
            Segment(
                start=s.start + seconds,
                end=s.end + seconds,
                text=s.text,
                words=[Word(text=w.text, start=w.start + seconds, end=w.end + seconds) for w in s.words],
            )
            for s in transcript.segments
        ],
    )


def _transcribe_mlx(audio, setup: hardware.WhisperSetup, language: str | None) -> Transcript:
    import mlx_whisper  # import tardio: só existe em Mac com chip Apple

    result = mlx_whisper.transcribe(
        audio, path_or_hf_repo=setup.model, word_timestamps=True, language=language, verbose=False
    )
    segments = [
        Segment(
            start=s["start"],
            end=s["end"],
            text=s["text"].strip(),
            words=[
                Word(text=w["word"].strip(), start=w["start"], end=w["end"])
                for w in s.get("words", [])
                if w["word"].strip()
            ],
        )
        for s in result["segments"]
    ]
    return Transcript(language=result.get("language", language or ""), segments=segments)


@functools.cache
def _faster_whisper_model(model: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel

    return WhisperModel(model, device=device, compute_type=compute_type)


def _load_faster_whisper(setup: hardware.WhisperSetup):
    try:
        return _faster_whisper_model(setup.model, setup.device, setup.compute_type or "default")
    except Exception:
        if setup.device != "cuda":
            raise
        # Placa NVIDIA detectada, mas faltam bibliotecas CUDA/cuDNN: segue na CPU em vez de falhar.
        log.warning("Não foi possível usar a GPU NVIDIA; transcrevendo na CPU (mais lento).", exc_info=True)
        return _faster_whisper_model(setup.model, "cpu", "int8")


SAMPLE_RATE = 16000  # o Whisper trabalha com áudio mono a 16 kHz


def load_audio(video: Path, start: float = 0.0, end: float | None = None):
    """Extrai o áudio (mono, 16 kHz) com o FFmpeg, opcionalmente só de `start` até `end` (segundos do arquivo)."""
    import numpy as np

    raw = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            *(["-ss", f"{start:.3f}"] if start else []),
            *(["-to", f"{end:.3f}"] if end is not None else []),
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "s16le",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def _transcribe_faster_whisper(audio, setup: hardware.WhisperSetup, language: str | None) -> Transcript:
    model = _load_faster_whisper(setup)
    segments_iter, info = model.transcribe(audio, language=language, word_timestamps=True, vad_filter=True)
    return segments_from_faster_whisper(segments_iter, info.language or language or "")


def segments_from_faster_whisper(segments_iter, language: str) -> Transcript:
    segments = [
        Segment(
            start=s.start,
            end=s.end,
            text=s.text.strip(),
            words=[
                Word(text=w.word.strip(), start=w.start, end=w.end) for w in (s.words or []) if w.word.strip()
            ],
        )
        for s in segments_iter
    ]
    return Transcript(language=language, segments=segments)


def to_prompt_text(transcript: Transcript) -> str:
    """Formato compacto pro Claude: uma linha por segmento com o tempo em segundos."""
    return "\n".join(f"[{s.start:.1f}-{s.end:.1f}] {s.text}" for s in transcript.segments)
