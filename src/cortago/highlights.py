"""Claude lê a transcrição e escolhe os melhores momentos para Shorts."""

import json

import anthropic
from pydantic import BaseModel

from cortago import config
from cortago.download import SourceInfo
from cortago.transcribe import Transcript, to_prompt_text


class Clip(BaseModel):
    start: float
    end: float
    title: str
    hook: str
    description: str
    hashtags: list[str]
    score: int
    reason: str


SYSTEM = """Você é editor de um canal brasileiro de YouTube Shorts sobre GTA 6.
Sua tarefa é encontrar, na transcrição de um vídeo, os trechos com mais potencial de virar Short.

Um bom corte:
- se sustenta sozinho, sem o espectador precisar do contexto do resto do vídeo;
- prende nos primeiros 2 segundos (revelação, opinião forte, reação, informação nova, humor);
- termina numa frase completa, de preferência num punchline ou conclusão;
- dura entre {min_s} e {max_s} segundos.

Regras de tempo: use apenas os tempos que aparecem na transcrição. Comece no início de uma frase
e termine no fim de uma frase. Os cortes não podem se sobrepor.

Para cada corte escreva em português do Brasil:
- title: título de Short com até 70 caracteres, chamativo mas sem mentir sobre o conteúdo;
- hook: texto curto (até 6 palavras) para aparecer na tela nos primeiros segundos;
- description: 1–2 frases sobre o corte;
- hashtags: 3 a 5, sem o '#';
- score: 1 a 10, potencial de viralizar;
- reason: por que esse trecho funciona, em uma frase.

Ordene do maior score para o menor."""

SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "title": {"type": "string"},
                    "hook": {"type": "string"},
                    "description": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                    "score": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["start", "end", "title", "hook", "description", "hashtags", "score", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}


def pick_clips(
    source: SourceInfo,
    transcript: Transcript,
    count: int,
    min_s: int = 20,
    max_s: int = 60,
) -> tuple[list[Clip], anthropic.types.beta.BetaUsage]:
    client = anthropic.Anthropic()

    user = (
        f"Vídeo: {source.title}\nCanal: {source.channel}\nDuração: {source.duration:.0f}s\n\n"
        f"Escolha até {count} cortes.\n\n<transcricao>\n{to_prompt_text(transcript)}\n</transcricao>"
    )

    response = client.beta.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=16000,
        system=SYSTEM.format(min_s=min_s, max_s=max_s),
        messages=[{"role": "user", "content": user}],
        output_config={
            "effort": config.CLAUDE_EFFORT,
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        # Se o modelo recusar por falso positivo de segurança, a API tenta de novo noutro modelo.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )

    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude recusou a requisição: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Resposta cortada por max_tokens; peça menos cortes.")

    text = next(b.text for b in response.content if b.type == "text")
    clips = [Clip.model_validate(c) for c in json.loads(text)["clips"]]
    clips = [_snap_to_words(c, transcript) for c in clips]
    clips = [c for c in clips if c.end - c.start >= min_s * 0.75]
    return sorted(clips, key=lambda c: -c.score)[:count], response.usage


def _snap_to_words(clip: Clip, transcript: Transcript, pad: float = 0.15) -> Clip:
    """Ajusta início/fim para bordas de palavras reais, evitando cortar sílabas."""
    words = transcript.words
    inside = [w for w in words if w.end > clip.start - 0.5 and w.start < clip.end + 0.5]
    if not inside:
        return clip
    return clip.model_copy(
        update={
            "start": max(0.0, inside[0].start - pad),
            "end": inside[-1].end + pad,
        }
    )
