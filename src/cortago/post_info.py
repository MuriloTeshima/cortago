"""Campos prontos para colar no formulário de envio do YouTube Studio."""

from dataclasses import dataclass

from cortago import config, music, timecode
from cortago.db import Clip, Job

# Limites do formulário do YouTube Studio.
TITLE_LIMIT = 100
DESCRIPTION_LIMIT = 5000
TAGS_LIMIT = 500


@dataclass(frozen=True)
class PostInfo:
    title: str
    description: str
    tags: str  # separadas por vírgula, como o campo "Tags" do YouTube espera
    category: str
    language: str

    @property
    def title_over(self) -> bool:
        return len(self.title) > TITLE_LIMIT

    @property
    def description_over(self) -> bool:
        return len(self.description) > DESCRIPTION_LIMIT


def _hashtag(tag: str) -> str:
    return "#" + tag.strip().lstrip("#").replace(" ", "")


def tags_length(tags: list[str]) -> int:
    """Como o YouTube conta: vírgulas entre tags e aspas em volta das que têm espaço."""
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(len(tags) - 1, 0)


def build_tags(clip: Clip) -> str:
    candidates = [t.strip().lstrip("#") for t in clip.hashtags]
    candidates += [t.strip() for t in config.YT_EXTRA_TAGS.split(",")]
    tags: list[str] = []
    seen: set[str] = set()
    for tag in candidates:
        if not tag or tag.lower() in seen:
            continue
        if tags_length([*tags, tag]) > TAGS_LIMIT:
            break
        tags.append(tag)
        seen.add(tag.lower())
    return ", ".join(tags)


def build_description(clip: Clip, job: Job) -> str:
    # O link abre o vídeo original no instante do corte (YouTube e Twitch).
    link = timecode.at(job.url, job.source_offset + clip.start) if job.url else None
    credit = f"Créditos: {job.channel}" + (f" — {link}" if link else "")
    music_credit = music.credit(clip.music_track) if clip.music_track else None
    if music_credit:
        credit += f"\nMúsica: {music_credit}"
    hashtags = " ".join(_hashtag(t) for t in clip.hashtags if t.strip("# "))
    parts = [clip.description.strip(), credit, hashtags]
    return "\n\n".join(p for p in parts if p)


def build(clip: Clip, job: Job) -> PostInfo:
    return PostInfo(
        title=clip.title.strip(),
        description=build_description(clip, job),
        tags=build_tags(clip),
        category=config.YT_CATEGORY,
        language=config.YT_LANGUAGE,
    )
