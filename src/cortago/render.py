"""Recorta o trecho, converte para 9:16 e grava as legendas com FFmpeg."""

import subprocess
from pathlib import Path

from cortago import config

LAYOUTS: tuple[str, ...] = ("blur", "crop")

# Ducking: quanto a música abaixa quando há voz. Calibrado pra ~10 dB de redução numa fala normal.
DUCK_THRESHOLD = 0.07
DUCK_RATIO = 4


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
        f"[1:a]aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,volume={volume:.3f},"
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
        volume = config.MUSIC_VOLUME if music_volume is None else music_volume
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
        "-c:v",
        config.VIDEO_ENCODER,
        "-b:v",
        config.VIDEO_BITRATE,
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
    subprocess.run(cmd, check=True, cwd=ass.parent, capture_output=True, text=True)


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
    ).stdout
    return bool(out.strip())


def media_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return float(out.strip())
