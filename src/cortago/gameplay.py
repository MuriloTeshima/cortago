"""Gameplay de fundo: um segundo vídeo (sem som) que alterna com a pessoa falando, para o corte não ficar monótono.

A voz vem sempre do vídeo principal. A imagem só troca entre frases, em blocos de alguns segundos, e o
gancho (começo do corte) mostra sempre quem fala. Quem decide em quais frases entra a gameplay é o Claude
(na mesma chamada que escolhe os cortes); sem essa indicação, alterna sozinho. Na timeline dá para trocar
bloco a bloco (`Clip.edit["gameplay"]`).

Tempos em segundos do **arquivo baixado**, como `Clip.start/end`.
"""

from cortago.effects import Segment
from cortago.transcribe import Word

# none: sem gameplay; alternar: tela cheia, alternando com quem fala; dividida: quem fala em cima, gameplay embaixo.
MODES = ("none", "alternar", "dividida")
MODE_LABELS = {"none": "Sem gameplay", "alternar": "Alternar com quem fala", "dividida": "Tela dividida"}

HOOK_SECONDS = 3.0  # o gancho mostra sempre quem fala
MIN_BLOCK = 2.0  # troca de imagem mais rápida que isso cansa
MAX_BLOCK = 8.0  # bloco maior que isso é dividido (numa pausa entre palavras)
SENTENCE_GAP = 0.45  # pausa que conta como fim de frase mesmo sem pontuação
MIN_HINT_SHARE = 0.5  # parte do bloco coberta pela indicação do Claude para virar gameplay


def _ends_sentence(word: Word) -> bool:
    return word.text.rstrip().endswith((".", "!", "?", "…"))


def blocks(words: list[Word], start: float, end: float) -> list[Segment]:
    """Divide o corte em blocos de frase (cobrindo o corte inteiro). A imagem só troca nas bordas deles."""
    inside = [w for w in words if w.end > start and w.start < end]
    if end - start <= MIN_BLOCK or not inside:
        return [(start, end)]

    # Pontos de troca possíveis: entre duas palavras, no meio da pausa.
    cuts: list[tuple[float, bool]] = []  # (instante, é fim de frase)
    for prev, nxt in zip(inside, inside[1:], strict=False):
        cuts.append(
            ((prev.end + nxt.start) / 2, _ends_sentence(prev) or nxt.start - prev.end >= SENTENCE_GAP)
        )

    bounds = [start]
    last_free: float | None = (
        None  # último ponto entre palavras desde a última borda (para dividir blocos longos)
    )
    for t, sentence in cuts:
        if t - bounds[-1] > MAX_BLOCK and last_free is not None and last_free - bounds[-1] >= MIN_BLOCK:
            bounds.append(last_free)
        if sentence and t - bounds[-1] >= MIN_BLOCK:
            bounds.append(t)
            last_free = None
        else:
            last_free = t
    if end - bounds[-1] < MIN_BLOCK and len(bounds) > 1:
        bounds.pop()  # o resto curto vai para o último bloco
    bounds.append(end)
    return list(zip(bounds, bounds[1:], strict=False))


def covered(block: Segment, spans: list[Segment]) -> float:
    a, b = block
    return sum(max(0.0, min(b, y) - max(a, x)) for x, y in spans)


def merge(spans: list[Segment]) -> list[Segment]:
    """Junta intervalos encostados ou sobrepostos."""
    out: list[Segment] = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + 1e-6:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def choose(block_list: list[Segment], hints: list[Segment] | None, start: float) -> list[bool]:
    """Quais blocos mostram a gameplay. Com `hints` (do Claude), os blocos cobertos por eles; senão, alterna."""
    flags = []
    for i, block in enumerate(block_list):
        if block[0] < start + HOOK_SECONDS or i == 0:
            flags.append(False)  # gancho: quem fala
        elif hints is not None:
            flags.append(covered(block, hints) >= MIN_HINT_SHARE * (block[1] - block[0]))
        else:
            flags.append(not flags[-1])
    return flags


def plan(words: list[Word], start: float, end: float, hints: list[Segment] | None = None) -> list[Segment]:
    """Intervalos (tempo do arquivo) em que a gameplay ocupa a tela."""
    bl = blocks(words, start, end)
    return merge([b for b, on in zip(bl, choose(bl, hints, start), strict=True) if on])


def manual_spans(edit: dict | None) -> list[Segment] | None:
    if not edit or edit.get("gameplay") is None:
        return None
    return [(float(a), float(b)) for a, b in edit["gameplay"]]


def hints_of(clip) -> list[Segment] | None:
    if clip.gameplay_hints is None:
        return None
    return [(float(a), float(b)) for a, b in clip.gameplay_hints]


def effective_spans(clip, words: list[Word]) -> list[Segment]:
    """Quando a gameplay aparece neste corte: ajuste manual > indicação do Claude > alternância automática."""
    if clip.gameplay_mode == "none":
        return []
    if clip.gameplay_mode == "dividida":
        return [(clip.start, clip.end)]  # a tela dividida fica o corte todo
    manual = manual_spans(clip.edit)
    if manual is not None:
        return manual
    return plan(words, clip.start, clip.end, hints_of(clip))


def validate_spans(spans: list[Segment], start: float, end: float) -> list[Segment]:
    clean = []
    for a, b in spans:
        a, b = round(float(a), 3), round(float(b), 3)
        if b <= a:
            raise ValueError("Bloco de gameplay inválido")
        a, b = max(a, start), min(b, end)
        if b > a:
            clean.append((a, b))
    return merge(clean)


def to_output(spans: list[Segment], start: float, segments: list[Segment] | None) -> list[Segment]:
    """Converte intervalos do arquivo para o tempo do vídeo final (sem as partes removidas)."""
    from cortago.effects import remap

    rel = [(a - start, b - start) for a, b in segments] if segments else None
    out = []
    for a, b in spans:
        if rel:
            x, y = remap(a - start, rel), remap(b - start, rel)
        else:
            x, y = a - start, b - start
        if y - x > 0.05:
            out.append((round(max(x, 0.0), 3), round(y, 3)))
    return merge(out)


def enable_expr(spans: list[Segment]) -> str:
    """Expressão `enable` do FFmpeg: verdadeira dentro de qualquer um dos intervalos."""
    return "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in spans) or "0"
