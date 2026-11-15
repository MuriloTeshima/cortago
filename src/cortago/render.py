"""Recorta o trecho, converte para 9:16 e grava as legendas com FFmpeg."""

import subprocess
from pathlib import Path

from cortago import config

LAYOUTS: tuple[str, ...] = ("blur", "crop")


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


def render_clip(source: Path, start: float, end: float, ass: Path, out: Path, layout: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(source.resolve()),
        "-t",
        f"{end - start:.3f}",
        "-filter_complex",
        _video_filter(layout, ass.name),
        "-map",
        "[v]",
        "-map",
        "0:a?",
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
