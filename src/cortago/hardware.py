"""Detecta o que o computador oferece e escolhe o melhor caminho para transcrever e codificar vídeo.

Mac com chip Apple → MLX + VideoToolbox. GPU NVIDIA → faster-whisper em CUDA + NVENC.
Intel/AMD → encoder de hardware deles (Quick Sync / AMF). Sem nada disso → CPU (faster-whisper + libx264).
Tudo pode ser forçado pelo .env (CORTAGO_WHISPER_BACKEND, CORTAGO_VIDEO_ENCODER).
"""

import functools
import platform
import shutil
import subprocess
from dataclasses import dataclass

from cortago import config

# Ordem de preferência dos encoders H.264 por sistema. libx264 (CPU) é o último recurso.
ENCODER_CANDIDATES = {
    "Darwin": ["h264_videotoolbox"],
    "Windows": ["h264_nvenc", "h264_qsv", "h264_amf"],
    "Linux": ["h264_nvenc", "h264_qsv"],
}
CPU_ENCODER = "libx264"


def is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def cuda_devices() -> int:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count()
    except Exception:
        return 0


@dataclass(frozen=True)
class WhisperSetup:
    backend: str  # "mlx" ou "faster-whisper"
    device: str  # "apple-gpu", "cuda" ou "cpu"
    model: str
    compute_type: str | None = None  # só faster-whisper


@functools.cache
def whisper_setup() -> WhisperSetup:
    backend = config.WHISPER_BACKEND or ("mlx" if is_apple_silicon() else "faster-whisper")
    if backend == "mlx":
        return WhisperSetup(
            "mlx", "apple-gpu", config.WHISPER_MODEL or "mlx-community/whisper-large-v3-turbo"
        )
    if backend != "faster-whisper":
        raise ValueError(f"CORTAGO_WHISPER_BACKEND inválido: {backend!r} (use mlx ou faster-whisper)")
    if cuda_devices() > 0:
        return WhisperSetup("faster-whisper", "cuda", config.WHISPER_MODEL or "large-v3-turbo", "float16")
    # Na CPU, int8 é bem mais rápido com perda mínima de precisão.
    return WhisperSetup("faster-whisper", "cpu", config.WHISPER_MODEL or "large-v3-turbo", "int8")


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def _encoder_works(encoder: str) -> bool:
    """O FFmpeg pode listar um encoder de hardware que a máquina não tem; só um teste real confirma."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=256x256:d=0.2",
                "-c:v",
                encoder,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@functools.cache
def video_encoder() -> str:
    if config.VIDEO_ENCODER:
        return config.VIDEO_ENCODER
    for encoder in ENCODER_CANDIDATES.get(platform.system(), []):
        if _encoder_works(encoder):
            return encoder
    return CPU_ENCODER


def encoder_args(encoder: str) -> list[str]:
    """Parâmetros de qualidade por encoder (cada um entende opções diferentes)."""
    if encoder == CPU_ENCODER:
        return ["-c:v", encoder, "-preset", "medium", "-crf", "20"]
    return ["-c:v", encoder, "-b:v", config.VIDEO_BITRATE]
