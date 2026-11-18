import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("CORTAGO_DATA_DIR", ROOT / "data"))
JOBS_DIR = DATA_DIR / "jobs"

CLAUDE_MODEL = os.getenv("CORTAGO_CLAUDE_MODEL", "claude-opus-5-5")
CLAUDE_EFFORT = os.getenv("CORTAGO_CLAUDE_EFFORT", "medium")

# Transcrição e encoder são escolhidos automaticamente conforme o computador (ver hardware.py).
# Deixe vazio para automático, ou force: CORTAGO_WHISPER_BACKEND=mlx|faster-whisper,
# CORTAGO_WHISPER_MODEL=<modelo>, CORTAGO_VIDEO_ENCODER=libx264|h264_nvenc|h264_videotoolbox|...
WHISPER_BACKEND = os.getenv("CORTAGO_WHISPER_BACKEND", "")
WHISPER_MODEL = os.getenv("CORTAGO_WHISPER_MODEL", "")
VIDEO_ENCODER = os.getenv("CORTAGO_VIDEO_ENCODER", "")
VIDEO_BITRATE = os.getenv("CORTAGO_VIDEO_BITRATE", "8M")

OUT_W, OUT_H = 1080, 1920

# Músicas de fundo: coloque faixas livres de direitos (ex.: Biblioteca de áudio do YouTube) nesta pasta.
# Um .txt com o mesmo nome da faixa vira o crédito na descrição do corte.
MUSIC_DIR = Path(os.getenv("CORTAGO_MUSIC_DIR", DATA_DIR / "music"))
# Quantos dB a música fica abaixo do áudio do vídeo (medido em cada corte). Maior = música mais baixa.
# Durante a fala ela abaixa mais ~10 dB sozinha (ducking). Ajuste fino por corte é feito na interface.
MUSIC_GAP_DB = float(os.getenv("CORTAGO_MUSIC_GAP_DB", "12"))

# --- Personalização por canal (a ferramenta é genérica; cada canal ajusta no seu .env) ---

# Quem é o canal, em uma frase. Vai no prompt do Claude e orienta a escolha dos cortes.
CHANNEL_CONTEXT = os.getenv(
    "CORTAGO_CHANNEL_CONTEXT", "um canal brasileiro de cortes de games no YouTube Shorts"
)
# Cor da palavra sendo falada na legenda e da caixa do gancho (#RRGGBB).
HIGHLIGHT_COLOR = os.getenv("CORTAGO_HIGHLIGHT_COLOR", "#FFE500")
HOOK_BOX_COLOR = os.getenv("CORTAGO_HOOK_BOX_COLOR", "#000000")

# Campos que você marca à mão no YouTube Studio ao postar (aparecem no painel "Postar no YouTube").
YT_CATEGORY = os.getenv("CORTAGO_YT_CATEGORY", "Jogos")
YT_LANGUAGE = os.getenv("CORTAGO_YT_LANGUAGE", "Português (Brasil)")
# Tags extras adicionadas a todo corte, separadas por vírgula (ex.: "games,cortes de games").
YT_EXTRA_TAGS = os.getenv("CORTAGO_YT_EXTRA_TAGS", "")


def _flag(name: str, default: bool) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in ("1", "true", "sim", "yes", "on")


# Efeitos de retenção aplicados por padrão nos cortes novos (cada corte pode mudar na edição).
FX_JUMP_CUTS = _flag("CORTAGO_FX_JUMP_CUTS", True)
FX_INTRO_ZOOM = os.getenv("CORTAGO_FX_INTRO_ZOOM", "suave")  # none | suave | forte
FX_HOOK_ANIM = _flag("CORTAGO_FX_HOOK_ANIM", True)
FX_HOOK_SFX = os.getenv("CORTAGO_FX_HOOK_SFX", "whoosh")  # none | whoosh | pop | impact
FX_PROGRESS_BAR = _flag("CORTAGO_FX_PROGRESS_BAR", True)
