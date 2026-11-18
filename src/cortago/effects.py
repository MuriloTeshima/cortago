"""Efeitos de retenção: cortes de silêncio, zoom de entrada, gancho animado, som no gancho e barra de progresso.

Tudo é calculado aqui e aplicado pelo render (FFmpeg) e pelas legendas (ASS).
"""

from dataclasses import dataclass

from cortago.transcribe import Word

# Zoom de entrada: quanto o vídeo começa ampliado. Volta ao normal em INTRO_ZOOM_SECONDS.
INTRO_ZOOMS = {"none": 0.0, "suave": 0.10, "forte": 0.22}
INTRO_ZOOM_SECONDS = 0.6

# Sons do gancho, gerados pelo próprio FFmpeg (não dependem de arquivos nem de licença de terceiros).
# Cada um é uma fonte lavfi; o volume final é ajustado na mixagem.
HOOK_SFX = {
    "none": None,
    "whoosh": (
        "anoisesrc=d=0.7:c=pink:a=0.8:r=48000,highpass=f=250,lowpass=f=4000,"
        "volume='sin(PI*t/0.7)':eval=frame,afade=t=in:d=0.25,afade=t=out:st=0.4:d=0.3"
    ),
    "pop": "aevalsrc='0.9*sin(2*PI*(600+900*exp(-t*40))*t)*exp(-t*30)':d=0.18:s=48000",
    "impact": (
        "aevalsrc='0.9*sin(2*PI*(45+90*exp(-t*9))*t)*exp(-t*6)+0.25*(random(0)*2-1)*exp(-t*25)':d=0.7:s=48000"
    ),
}
SFX_GAIN = 0.35  # o som acompanha o gancho; não pode competir com a fala

# Cortes de silêncio: pausas maiores que MAX_PAUSE saem do vídeo, mantendo PAD de respiro em cada lado.
MAX_PAUSE = 0.35
PAD = 0.08
TAIL = 0.25  # respiro no fim, pra não terminar seco
MIN_SEGMENT = 0.12

PROGRESS_BAR_HEIGHT = 10


@dataclass(frozen=True)
class Effects:
    jump_cuts: bool = False
    intro_zoom: str = "none"
    hook_anim: bool = False
    hook_sfx: str = "none"
    progress_bar: bool = False

    def __post_init__(self) -> None:
        if self.intro_zoom not in INTRO_ZOOMS:
            raise ValueError(f"zoom de entrada inválido: {self.intro_zoom!r}")
        if self.hook_sfx not in HOOK_SFX:
            raise ValueError(f"som do gancho inválido: {self.hook_sfx!r}")

    @classmethod
    def from_clip(cls, clip) -> "Effects":
        return cls(
            jump_cuts=clip.jump_cuts,
            intro_zoom=clip.intro_zoom,
            hook_anim=clip.hook_anim,
            hook_sfx=clip.hook_sfx,
            progress_bar=clip.progress_bar,
        )


def defaults() -> dict:
    """Efeitos padrão para cortes novos, vindos do .env (valores inválidos viram "none")."""
    from cortago import config

    return {
        "jump_cuts": config.FX_JUMP_CUTS,
        "intro_zoom": config.FX_INTRO_ZOOM if config.FX_INTRO_ZOOM in INTRO_ZOOMS else "none",
        "hook_anim": config.FX_HOOK_ANIM,
        "hook_sfx": config.FX_HOOK_SFX if config.FX_HOOK_SFX in HOOK_SFX else "none",
        "progress_bar": config.FX_PROGRESS_BAR,
    }


Segment = tuple[float, float]


def _overlap(a: Segment, b: Segment) -> Segment | None:
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return (lo, hi) if hi > lo else None


def speech_segments(
    words: list[Word], start: float, end: float, quiet: list[Segment] | None = None
) -> list[Segment]:
    """Trechos do corte (em segundos do vídeo original) que ficam, sem as pausas longas.

    Uma pausa só sai se não houver palavras **e** o áudio estiver quieto (`quiet`, vindo da detecção de
    silêncio). Assim, som de jogo, trailer ou música do vídeo original nunca é cortado só porque ninguém
    fala. Sem `quiet`, considera todo intervalo sem palavras como silêncio.
    """
    inside = [w for w in words if w.end > start and w.start < end]
    if not inside:
        return [(start, end)]

    # Intervalos sem palavras: antes da primeira, entre palavras e depois da última.
    gaps: list[Segment] = [(start, inside[0].start)]
    gaps += [(prev.end, nxt.start) for prev, nxt in zip(inside, inside[1:], strict=False)]
    gaps.append((inside[-1].end, end))

    cuts: list[Segment] = []
    for i, gap in enumerate(gaps):
        candidates = [gap] if quiet is None else [o for q in quiet if (o := _overlap(gap, q))]
        for lo, hi in candidates:
            if hi - lo <= MAX_PAUSE:
                continue
            is_first, is_last = i == 0, i == len(gaps) - 1
            cut_lo = lo if is_first and lo <= start else lo + PAD
            cut_hi = hi if is_last and hi >= end else hi - PAD
            if is_last:
                cut_lo = max(cut_lo, inside[-1].end + TAIL)
            if cut_hi - cut_lo > 0:
                cuts.append((cut_lo, cut_hi))

    segments: list[Segment] = []
    cursor = start
    for lo, hi in sorted(cuts):
        if lo > cursor:
            segments.append((cursor, lo))
        cursor = max(cursor, hi)
    if cursor < end:
        segments.append((cursor, end))
    return [(a, b) for a, b in segments if b - a >= MIN_SEGMENT] or [(start, end)]


def quiet_threshold_db(clip_lufs: float | None) -> float:
    """Abaixo de quanto (dB) o áudio conta como silêncio: 20 dB abaixo do volume do próprio corte."""
    if clip_lufs is None:
        return -40.0
    return min(max(clip_lufs - 20, -55.0), -30.0)


def parse_silences(silencedetect_log: str, offset: float = 0.0) -> list[Segment]:
    """Extrai os intervalos do filtro silencedetect do FFmpeg (somando `offset` para voltar ao tempo original)."""
    import re

    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", silencedetect_log)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", silencedetect_log)]
    pairs = list(zip(starts, ends, strict=False))
    if len(starts) > len(ends):  # silêncio até o fim do trecho analisado
        pairs.append((starts[-1], float("inf")))
    return [(max(a, 0.0) + offset, b + offset) for a, b in pairs]


def total_duration(segments: list[Segment]) -> float:
    return sum(b - a for a, b in segments)


def remap(t: float, segments: list[Segment]) -> float:
    """Converte um instante do vídeo original para o tempo do vídeo já sem as pausas.

    Instantes que caem numa pausa removida vão para o começo do trecho seguinte.
    """
    elapsed = 0.0
    for a, b in segments:
        if t < a:
            return elapsed
        if t <= b:
            return elapsed + (t - a)
        elapsed += b - a
    return elapsed


def zoom_scale_expr(amount: float, out_size: int) -> str:
    """Expressão do FFmpeg para o tamanho a cada quadro: começa ampliado e volta ao normal (ease-out)."""
    factor = f"(1+{amount:g}*pow(max(0,1-t/{INTRO_ZOOM_SECONDS:g}),2))"
    return f"trunc({out_size}*{factor}/2)*2"


def hook_override(animated: bool) -> str:
    """Tags ASS do gancho: entra 35% maior e encaixa no tamanho final, com fade."""
    if not animated:
        return ""
    return r"{\fad(80,250)\fscx135\fscy135\t(0,220,\fscx100\fscy100)}"
