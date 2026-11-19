"""Timeline de um corte: trechos que entram no vídeo, correções de legenda e a janela exibida no editor.

Tudo em segundos do **arquivo baixado** (como `Clip.start/end`). O documento de edição (`Clip.edit`) guarda só
o que foi ajustado à mão; o resto continua automático.
"""

from cortago.effects import MIN_SEGMENT, Segment
from cortago.transcribe import Word

CONTEXT_SECONDS = 15.0  # quanto do vídeo aparece antes e depois do corte, para dar espaço a estender
MAX_WORD_LEN = 40


def word_key(word: Word) -> str:
    """Identifica a palavra pelo início (2 casas): estável enquanto a transcrição do vídeo não mudar."""
    return f"{word.start:.2f}"


def apply_word_fixes(words: list[Word], fixes: dict[str, str] | None) -> list[Word]:
    """Troca o texto das palavras corrigidas à mão."""
    if not fixes:
        return words
    return [w.model_copy(update={"text": fixes[word_key(w)]}) if word_key(w) in fixes else w for w in words]


def manual_segments(edit: dict | None) -> list[Segment] | None:
    if not edit or not edit.get("segments"):
        return None
    return [(float(a), float(b)) for a, b in edit["segments"]]


def word_fixes(edit: dict | None) -> dict[str, str]:
    return dict((edit or {}).get("words") or {})


def validate_segments(segments: list[Segment], file_end: float | None) -> list[Segment]:
    """Ordena, recusa sobreposição e trechos curtos ou fora do vídeo. Devolve a lista normalizada."""
    if not segments:
        raise ValueError("O corte precisa de pelo menos um trecho")
    ordered = sorted((round(float(a), 3), round(float(b), 3)) for a, b in segments)
    for a, b in ordered:
        if a < 0 or (file_end is not None and b > file_end + 0.5):
            raise ValueError("Há um trecho fora do vídeo")
        if b - a < MIN_SEGMENT:
            raise ValueError(f"Cada trecho precisa ter pelo menos {MIN_SEGMENT:g}s")
    for (_, prev_end), (nxt_start, _) in zip(ordered, ordered[1:], strict=False):
        if nxt_start < prev_end:
            raise ValueError("Os trechos não podem se sobrepor")
    return ordered


def validate_word_fixes(fixes: dict[str, str]) -> dict[str, str]:
    clean = {}
    for key, text in fixes.items():
        text = " ".join(str(text).split())
        if not text:
            raise ValueError("Uma palavra corrigida não pode ficar vazia")
        if len(text) > MAX_WORD_LEN:
            raise ValueError(f"Cada palavra corrigida pode ter até {MAX_WORD_LEN} caracteres")
        clean[f"{float(key):.2f}"] = text
    return clean


def display_window(start: float, end: float, file_end: float | None) -> tuple[float, float]:
    """Trecho do vídeo mostrado na timeline: o corte com uma margem de cada lado."""
    lo = max(start - CONTEXT_SECONDS, 0.0)
    hi = end + CONTEXT_SECONDS
    if file_end is not None:
        hi = min(hi, file_end)
    return lo, hi
