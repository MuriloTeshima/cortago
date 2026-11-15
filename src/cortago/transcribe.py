"""Transcrição local com timestamps por palavra (mlx-whisper, roda na GPU do M4)."""

from pathlib import Path

from pydantic import BaseModel

from cortago import config


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


def transcribe(video: Path, cache: Path, language: str | None = None) -> Transcript:
    if cache.exists():
        return Transcript.model_validate_json(cache.read_text())

    import mlx_whisper  # import tardio: carrega MLX só quando precisa

    result = mlx_whisper.transcribe(
        str(video),
        path_or_hf_repo=config.WHISPER_MODEL,
        word_timestamps=True,
        language=language,
        verbose=False,
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
    transcript = Transcript(language=result.get("language", language or ""), segments=segments)
    cache.write_text(transcript.model_dump_json(indent=1))
    return transcript


def to_prompt_text(transcript: Transcript) -> str:
    """Formato compacto pro Claude: uma linha por segmento com o tempo em segundos."""
    return "\n".join(f"[{s.start:.1f}-{s.end:.1f}] {s.text}" for s in transcript.segments)
