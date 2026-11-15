import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("CORTAGO_DATA_DIR", ROOT / "data"))
JOBS_DIR = DATA_DIR / "jobs"

CLAUDE_MODEL = os.getenv("CORTAGO_CLAUDE_MODEL", "claude-opus-5-5")
CLAUDE_EFFORT = os.getenv("CORTAGO_CLAUDE_EFFORT", "medium")

# large-v3-turbo: ótima precisão em PT/EN e rápido no Apple Silicon via MLX.
WHISPER_MODEL = os.getenv("CORTAGO_WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo")

# Encoder de hardware do Apple Silicon. Troque por "libx264" se preferir qualidade/tamanho.
VIDEO_ENCODER = os.getenv("CORTAGO_VIDEO_ENCODER", "h264_videotoolbox")
VIDEO_BITRATE = os.getenv("CORTAGO_VIDEO_BITRATE", "8M")

OUT_W, OUT_H = 1080, 1920

# Músicas de fundo: coloque faixas livres de direitos (ex.: Biblioteca de áudio do YouTube) nesta pasta.
# Um .txt com o mesmo nome da faixa vira o crédito na descrição do corte.
MUSIC_DIR = Path(os.getenv("CORTAGO_MUSIC_DIR", DATA_DIR / "music"))
# Quantos dB a música fica abaixo do áudio do vídeo (medido em cada corte). Maior = música mais baixa.
# Durante a fala ela abaixa mais ~10 dB sozinha (ducking). Ajuste fino por corte é feito na interface.
MUSIC_GAP_DB = float(os.getenv("CORTAGO_MUSIC_GAP_DB", "12"))
