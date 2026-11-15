"""Recorta o trecho, converte para 9:16 e grava as legendas com FFmpeg."""

import subprocess
from pathlib import Path

from cortago import config, hardware

LAYOUTS: tuple[str, ...] = ("blur", "crop")

# Ducking: quanto a música abaixa quando há voz. Calibrado pra ~10 dB de redução numa fala normal.
DUCK_THRESHOLD = 0.07
DUCK_RATIO = 4

# A música é normalizada nesse nível antes do volume (loudnorm no filtro de áudio).
MUSIC_REF_LUFS = -16.0
# Limites do nível da música nas pausas, pra vídeos muito altos ou muito baixos não gerarem extremos.
MUSIC_MIN_LUFS, MUSIC_MAX_LUFS = -40.0, -20.0
# Nível usado quando o vídeo não tem áudio (a música vira o único som).
MUSIC_NO_VOICE_LUFS = -20.0


def _video_filter(layout: str, ass_name: str) -> str:
    W, H = config.OUT_W, config.OUT_H
    if layout == "crop":
        # Corta o centro do quadro: bom pra facecam/pessoa falando, ruim pra HUD de gameplay.
        return f"[0:v]scale=-2:{H},crop={W}:{H},ass={ass_name}[v]"
    # Vídeo inteiro no meio, com fundo desfocado: preserva HUD, mapa e legenda do vídeo original.
    return (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=25:3,eq=brightness=-0.08[bgb];"
        f"[fg]scale={W}:-2[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,ass={ass_name}[v]"
    )


def _audio_filter(duration: float, has_voice: bool, volume: float) -> str:
    """Música em volume baixo, com fade, que abaixa sozinha quando há voz (ducking por sidechain)."""
    fade_out = max(duration - 1.5, 0)
    music = (
        # loudnorm deixa toda faixa no mesmo nível (-16 LUFS) antes do volume, independente da masterização.
        f"[1:a]aresample=48000,loudnorm=I={MUSIC_REF_LUFS:g}:TP=-1.5:LRA=11,aresample=48000,volume={volume:.3f},"
        f"afade=t=in:d=1,afade=t=out:st={fade_out:.3f}:d=1.5[music]"
    )
    if not has_voice:
        return f"{music};[music]anull[a]"
    return (
        f"{music};"
        "[0:a]aresample=48000,asplit=2[voice][keyraw];"
        # A chave do compressor é normalizada: o ducking fica igual em vídeo gravado alto ou baixo.
        # (só a chave; a voz que vai pro vídeo segue intacta)
        "[keyraw]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[key];"
        # release longo evita a música "bombear" entre uma palavra e outra.
        f"[music][key]sidechaincompress=threshold={DUCK_THRESHOLD}:ratio={DUCK_RATIO}:attack=15:release=600[ducked];"
        "[voice][ducked]amix=inputs=2:duration=first:normalize=0[a]"
    )


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
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = end - start
    inputs = ["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source.resolve())]
    graph = _video_filter(layout, ass.name)
    audio_map = ["-map", "0:a?"]

    if music is not None:
        # -stream_loop repete a faixa se ela for mais curta que o corte.
        inputs += ["-stream_loop", "-1", "-ss", f"{music_offset:.3f}", "-i", str(music.resolve())]
        volume = auto_music_volume(None) if music_volume is None else music_volume
        graph += ";" + _audio_filter(duration, has_audio(source), volume)
        audio_map = ["-map", "[a]"]

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *inputs,
        "-filter_complex",
        graph,
        "-map",
        "[v]",
        *audio_map,
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
    subprocess.run(
        cmd, check=True, cwd=ass.parent, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def has_audio(path: Path) -> bool:
    out = subprocess.run(
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
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    return bool(out.strip())


def media_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
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
    out = subprocess.run(
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
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stderr
    return parse_integrated_loudness(out)


def parse_integrated_loudness(ebur128_log: str) -> float | None:
    """Extrai o 'I: -15.2 LUFS' do resumo do filtro ebur128 do FFmpeg."""
    import re

    values = re.findall(r"^\s*I:\s*(-?[\d.]+|-inf)\s*LUFS", ebur128_log, flags=re.MULTILINE)
    if not values or values[-1] == "-inf":
        return None
    value = float(values[-1])
    return None if value <= -69 else value
