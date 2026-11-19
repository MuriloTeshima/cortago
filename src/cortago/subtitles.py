"""Gera legendas .ass estilo Shorts: poucas palavras por vez, palavra atual destacada."""

from pathlib import Path

from cortago import config, effects
from cortago.transcribe import Word

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial Black,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,80,80,{caption_margin},1
Style: Hook,Arial Black,72,&H00FFFFFF,&H00FFFFFF,{hook_box},{hook_box},-1,0,0,0,100,100,0,0,3,18,0,8,80,80,{hook_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

RESET = r"{\c&H00FFFFFF&}"


def ass_color(hex_rgb: str, alpha: int = 0) -> str:
    """'#RRGGBB' → '&HAABBGGRR' (o ASS usa BGR e alpha invertido: 00 = opaco)."""
    h = hex_rgb.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"cor inválida: {hex_rgb!r} (use #RRGGBB)")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _highlight() -> str:
    return "{\\c" + ass_color(config.HIGHLIGHT_COLOR) + "&}"


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _chunks(words: list[Word], max_words: int = 3, max_gap: float = 0.6) -> list[list[Word]]:
    chunks: list[list[Word]] = []
    for w in words:
        if (
            chunks
            and len(chunks[-1]) < max_words
            and w.start - chunks[-1][-1].end < max_gap
            and not chunks[-1][-1].text.endswith((".", "!", "?"))
        ):
            chunks[-1].append(w)
        else:
            chunks.append([w])
    return chunks


def _clean(text: str) -> str:
    return text.upper().replace("{", "").replace("}", "").replace("\\", "")


def write_ass(
    words: list[Word],
    clip_start: float,
    clip_end: float,
    hook: str,
    out: Path,
    hook_seconds: float = 3.0,
    segments: list[effects.Segment] | None = None,
    hook_anim: bool = False,
    split: bool = False,
) -> None:
    """Legendas do corte. Com `segments` (cortes de silêncio), os tempos seguem o vídeo já sem as pausas.

    `split` (tela dividida): a legenda fica logo acima da emenda entre quem fala e a gameplay.
    """
    w, h = config.OUT_W, config.OUT_H
    lines = [
        HEADER.format(
            w=w,
            h=h,
            caption_margin=int(h * (0.47 if split else 0.28)),
            hook_margin=int(h * 0.12),
            hook_box=ass_color(config.HOOK_BOX_COLOR),
        )
    ]
    highlight = _highlight()

    if hook:
        anim = effects.hook_override(hook_anim)
        lines.append(f"Dialogue: 1,{_ts(0)},{_ts(hook_seconds)},Hook,,0,0,0,,{anim}{_clean(hook)}")

    inside = [x for x in words if x.end > clip_start and x.start < clip_end]
    if segments:
        clip_words = [
            x.model_copy(
                update={"start": effects.remap(x.start, segments), "end": effects.remap(x.end, segments)}
            )
            for x in inside
        ]
    else:
        clip_words = [
            x.model_copy(update={"start": x.start - clip_start, "end": x.end - clip_start}) for x in inside
        ]

    for chunk in _chunks(clip_words):
        chunk_end = chunk[-1].end
        for i, current in enumerate(chunk):
            # Cada palavra fica destacada do seu início até o início da próxima.
            end = chunk[i + 1].start if i + 1 < len(chunk) else chunk_end
            text = " ".join(
                f"{highlight}{_clean(x.text)}{RESET}" if j == i else _clean(x.text)
                for j, x in enumerate(chunk)
            )
            lines.append(f"Dialogue: 0,{_ts(current.start)},{_ts(end)},Caption,,0,0,0,,{text}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
