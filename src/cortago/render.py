"""Recorta o trecho, converte para 9:16 e grava as legendas com FFmpeg."""

from dataclasses import dataclass, field
from pathlib import Path

from cortago import cancel, config, effects, gameplay, hardware

LAYOUTS: tuple[str, ...] = ("blur", "crop")

# Ducking: quanto a música abaixa quando há voz. Calibrado pra ~10 dB de redução numa fala normal.
DUCK_THRESHOLD = 0.07
DUCK_RATIO = 4

# A música é normalizada nesse nível antes do volume (loudnorm no filtro de áudio).
MUSIC_REF_LUFS = -16.0
# Limites do nível da música nas pausas, pra vídeos muito altos ou muito baixos não gerarem extremos.
MUSIC_MIN_LUFS, MUSIC_MAX_LUFS = -40.0, -20.0
# Teto do limitador final (≈ -1 dBFS), pra evitar distorção quando a mixagem soma sons a um áudio já alto.
LIMITER_CEILING = 0.891

# Nível usado quando o vídeo não tem áudio (a música vira o único som).
MUSIC_NO_VOICE_LUFS = -20.0


@dataclass(frozen=True)
class Gameplay:
    """Gameplay de fundo de um corte: arquivo (sem som), ponto de início e quando aparece (tempo do vídeo final)."""

    path: Path
    offset: float = 0.0
    mode: str = "alternar"  # alternar | dividida
    spans: list[effects.Segment] = field(default_factory=list)


def _cover(vin: str, w: int, h: int, out: str) -> str:
    """Preenche w×h cortando o que sobrar (sem faixas pretas)."""
    return f"{vin}scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1{out}"


def _gameplay_filter(bg: Gameplay, gin: str, vin: str, layout: str, duration: float, out: str) -> str:
    """Monta a imagem com a gameplay: tela dividida (quem fala em cima) ou alternando em tela cheia."""
    W, H = config.OUT_W, config.OUT_H
    gp = f"{gin}trim=duration={duration:.3f},setpts=PTS-STARTPTS,"
    if bg.mode == "dividida":
        half = H // 2
        return (
            _cover(gp, W, half, "[gph];") + _cover(vin, W, half, "[top];") + f"[top][gph]vstack=inputs=2{out}"
        )
    return (
        _layout_filter(layout, vin, "[base];")
        + _cover(gp, W, H, "[gpf];")
        + f"[base][gpf]overlay=0:0:enable='{gameplay.enable_expr(bg.spans)}':eof_action=repeat{out}"
    )


def _layout_filter(layout: str, vin: str, out: str) -> str:
    W, H = config.OUT_W, config.OUT_H
    if layout == "crop":
        # Corta o centro do quadro: bom pra facecam/pessoa falando, ruim pra HUD de gameplay.
        return f"{vin}scale=-2:{H},crop={W}:{H}{out}"
    # Vídeo inteiro no meio, com fundo desfocado: preserva HUD, mapa e legenda do vídeo original.
    return (
        f"{vin}split=2[bg][fg];"
        f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=25:3,eq=brightness=-0.08[bgb];"
        f"[fg]scale={W}:-2[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2{out}"
    )


def _source_filter(segments: list[effects.Segment], has_voice: bool) -> tuple[list[str], str, str | None]:
    """Recorta os trechos (tempos relativos ao início do corte) e junta tudo, sem as pausas."""
    if len(segments) == 1:
        a, b = segments[0]
        parts = [f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[vsrc]"]
        if has_voice:
            parts.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[asrc]")
        return parts, "[vsrc]", "[asrc]" if has_voice else None

    n = len(segments)
    parts = ["[0:v]split=" + str(n) + "".join(f"[sv{i}]" for i in range(n))]
    if has_voice:
        parts.append("[0:a]asplit=" + str(n) + "".join(f"[sa{i}]" for i in range(n)))
    concat_in = ""
    for i, (a, b) in enumerate(segments):
        parts.append(f"[sv{i}]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}]")
        concat_in += f"[v{i}]"
        if has_voice:
            # Fades de 10 ms em cada emenda evitam estalos no áudio.
            fade_out = max(b - a - 0.01, 0)
            parts.append(
                f"[sa{i}]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:d=0.01,afade=t=out:st={fade_out:.3f}:d=0.01[a{i}]"
            )
            concat_in += f"[a{i}]"
    if has_voice:
        parts.append(f"{concat_in}concat=n={n}:v=1:a=1[vsrc][asrc]")
        return parts, "[vsrc]", "[asrc]"
    parts.append(f"{concat_in}concat=n={n}:v=1:a=0[vsrc]")
    return parts, "[vsrc]", None


def _music_filter(music_in: str, voice: str | None, duration: float, volume: float, out: str) -> str:
    """Música em volume baixo, com fade, que abaixa sozinha quando há voz (ducking por sidechain)."""
    fade_out = max(duration - 1.5, 0)
    music = (
        # loudnorm deixa toda faixa no mesmo nível (-16 LUFS) antes do volume, independente da masterização.
        f"{music_in}aresample=48000,loudnorm=I={MUSIC_REF_LUFS:g}:TP=-1.5:LRA=11,aresample=48000,volume={volume:.3f},"
        f"afade=t=in:d=1,afade=t=out:st={fade_out:.3f}:d=1.5[music]"
    )
    if voice is None:
        return f"{music};[music]anull{out}"
    return (
        f"{music};"
        f"{voice}aresample=48000,asplit=2[voice][keyraw];"
        # A chave do compressor é normalizada: o ducking fica igual em vídeo gravado alto ou baixo.
        # (só a chave; a voz que vai pro vídeo segue intacta)
        "[keyraw]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[key];"
        # release longo evita a música "bombear" entre uma palavra e outra.
        f"[music][key]sidechaincompress=threshold={DUCK_THRESHOLD}:ratio={DUCK_RATIO}:attack=15:release=600[ducked];"
        f"[voice][ducked]amix=inputs=2:duration=first:normalize=0{out}"
    )


def _audio_filter(duration: float, has_voice: bool, volume: float) -> str:
    """Compatível com o formato antigo: voz em [0:a], música em [1:a], saída em [a]."""
    return _music_filter("[1:a]", "[0:a]" if has_voice else None, duration, volume, "[a]")


def render_clip(
    source: Path,
    start: float,
    end: float,
    ass: Path,
    out: Path,
    layout: str,
    music: Path | None = None,
    music_offset: float = 0.0,
    music_volume: float | None = None,
    segments: list[effects.Segment] | None = None,
    fx: effects.Effects | None = None,
    gameplay: Gameplay | None = None,
) -> None:
    """Renderiza o corte. `segments` vem em segundos do vídeo original (padrão: o corte inteiro)."""
    fx = fx or effects.Effects()
    out.parent.mkdir(parents=True, exist_ok=True)
    rel = [(a - start, b - start) for a, b in (segments or [(start, end)])]
    duration = effects.total_duration(rel)
    has_voice = has_audio(source)
    W, H = config.OUT_W, config.OUT_H

    inputs = ["-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(source.resolve())]
    parts, vlabel, voice = _source_filter(rel, has_voice)

    # Vídeo: layout 9:16 (com ou sem gameplay) → zoom de entrada → legendas → barra de progresso.
    next_input = 1
    bg = gameplay
    if bg is not None and bg.mode != "dividida" and not bg.spans:
        bg = None  # nenhum bloco de gameplay: não precisa nem abrir o arquivo
    if bg is not None:
        # Gameplay sem som, repetida se for mais curta que o corte.
        inputs += ["-stream_loop", "-1", "-ss", f"{bg.offset:.3f}", "-i", str(bg.path.resolve())]
        parts.append(_gameplay_filter(bg, f"[{next_input}:v]", vlabel, layout, duration, "[vl]"))
        next_input += 1
    else:
        parts.append(_layout_filter(layout, vlabel, "[vl]"))
    vlabel = "[vl]"
    zoom = effects.INTRO_ZOOMS[fx.intro_zoom]
    if zoom:
        parts.append(
            f"{vlabel}scale=w='{effects.zoom_scale_expr(zoom, W)}':h='{effects.zoom_scale_expr(zoom, H)}'"
            f":eval=frame,crop={W}:{H}[vz]"
        )
        vlabel = "[vz]"
    parts.append(f"{vlabel}ass={ass.name}[vs]")
    vlabel = "[vs]"
    if fx.progress_bar:
        color = config.HIGHLIGHT_COLOR.lstrip("#")
        parts.append(f"color=c=0x{color}:s={W}x{effects.PROGRESS_BAR_HEIGHT}:d={duration:.3f}[bar]")
        parts.append(f"{vlabel}[bar]overlay=x='-w+w*t/{duration:.3f}':y=0:eval=frame:shortest=1[vp]")
        vlabel = "[vp]"

    # Áudio: voz (já sem as pausas) → música com ducking → som do gancho.
    alabel = voice
    if music is not None:
        # -stream_loop repete a faixa se ela for mais curta que o corte.
        inputs += ["-stream_loop", "-1", "-ss", f"{music_offset:.3f}", "-i", str(music.resolve())]
        volume = auto_music_volume(None) if music_volume is None else music_volume
        parts.append(_music_filter(f"[{next_input}:a]", alabel, duration, volume, "[am]"))
        alabel = "[am]"
        next_input += 1
    sfx = effects.HOOK_SFX[fx.hook_sfx]
    if sfx:
        inputs += ["-f", "lavfi", "-i", sfx]
        parts.append(f"[{next_input}:a]aresample=48000,volume={effects.SFX_GAIN},apad[sfx]")
        if alabel is None:
            alabel = "[sfx]"
        else:
            parts.append(
                f"{alabel}aresample=48000[base];[base][sfx]amix=inputs=2:duration=first:normalize=0[asfx]"
            )
            alabel = "[asfx]"
        next_input += 1

    if alabel is not None:
        # Limitador no fim: vídeos de live já vêm no teto (picos perto de 0 dB) e somar música/efeito
        # por cima distorce. Segura os picos em -1 dB sem mudar o volume percebido.
        parts.append(f"{alabel}alimiter=limit={LIMITER_CEILING}:attack=5:release=50:level=0[aout]")
        alabel = "[aout]"

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *inputs,
        "-filter_complex",
        ";".join(parts),
        "-map",
        vlabel,
        *(["-map", alabel] if alabel else []),
        "-t",
        f"{duration:.3f}",
        *hardware.encoder_args(hardware.video_encoder()),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(out.resolve()),
    ]
    # Roda dentro da pasta do .ass pra não precisar escapar o caminho no filtro do FFmpeg.
    cancel.run(cmd, check=True, cwd=ass.parent, text=True, encoding="utf-8", errors="replace")


def thumbnail(video: Path, out: Path, width: int = 360) -> None:
    """Miniatura do corte (um quadro perto do começo, já com legenda e gancho) para a galeria."""
    at = min(1.5, max(media_duration(video) / 3, 0))
    cancel.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{at:.2f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-2",
            "-q:v",
            "4",
            str(out),
        ],
        check=True,
    )


def waveform(source: Path, start: float, end: float, out: Path, width: int = 2000, height: int = 160) -> None:
    """Forma de onda do trecho (PNG transparente) para a timeline do editor."""
    cancel.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{end - start:.3f}",
            "-i",
            str(source),
            "-filter_complex",
            f"aformat=channel_layouts=mono,showwavespic=s={width}x{height}:colors=0x8B91A1:scale=sqrt:draw=full",
            "-frames:v",
            "1",
            str(out),
        ],
        check=True,
    )


def filmstrip(source: Path, start: float, end: float, out: Path, frames: int = 30, height: int = 90) -> None:
    """Faixa de miniaturas do trecho (lado a lado, igualmente espaçadas) para a timeline do editor."""
    duration = max(end - start, 0.1)
    cancel.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(source),
            "-vf",
            f"fps={frames}/{duration:.3f},scale=-2:{height},tile={frames}x1",
            "-frames:v",
            "1",
            "-q:v",
            "5",
            str(out),
        ],
        check=True,
    )


def has_audio(path: Path) -> bool:
    out = cancel.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    return bool(out.strip())


def media_duration(path: Path) -> float:
    out = cancel.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    return float(out.strip())


def auto_music_volume(video_lufs: float | None, gap_db: float | None = None, level: int = 100) -> float:
    """Volume (multiplicador) da música pra ela ficar `gap_db` abaixo do áudio do vídeo.

    `level` é o ajuste manual do corte em % (100 = automático, 0 = muda).
    """
    gap = config.MUSIC_GAP_DB if gap_db is None else gap_db
    target = MUSIC_NO_VOICE_LUFS if video_lufs is None else video_lufs - gap
    target = min(max(target, MUSIC_MIN_LUFS), MUSIC_MAX_LUFS)
    return 10 ** ((target - MUSIC_REF_LUFS) / 20) * max(level, 0) / 100


def measure_loudness(path: Path, start: float, duration: float) -> float | None:
    """Loudness integrado (LUFS) do áudio no trecho, ou None se não houver áudio audível."""
    if not has_audio(path):
        return None
    out = cancel.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(path),
            "-vn",
            "-af",
            "ebur128",
            "-f",
            "null",
            "-",
        ],
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stderr
    return parse_integrated_loudness(out)


def detect_quiet(path: Path, start: float, duration: float, threshold_db: float) -> list[effects.Segment]:
    """Intervalos (em segundos do vídeo original) em que o áudio fica abaixo de `threshold_db`."""
    if not has_audio(path):
        return [(start, start + duration)]
    out = cancel.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(path),
            "-vn",
            "-af",
            f"silencedetect=noise={threshold_db:.1f}dB:d={effects.MAX_PAUSE}",
            "-f",
            "null",
            "-",
        ],
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stderr
    return [(a, min(b, start + duration)) for a, b in effects.parse_silences(out, offset=start)]


def parse_integrated_loudness(ebur128_log: str) -> float | None:
    """Extrai o 'I: -15.2 LUFS' do resumo do filtro ebur128 do FFmpeg."""
    import re

    values = re.findall(r"^\s*I:\s*(-?[\d.]+|-inf)\s*LUFS", ebur128_log, flags=re.MULTILINE)
    if not values or values[-1] == "-inf":
        return None
    value = float(values[-1])
    return None if value <= -69 else value
