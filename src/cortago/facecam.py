"""Recorte da webcam: em vídeos em que a pessoa aparece numa miniatura (live, react, comentário de trailer),
o usuário marca uma vez onde fica a webcam e os cortes mostram essa área ampliada.

A área é guardada em `Job.facecam` como fração do quadro (0–1), então vale para qualquer resolução.
Cada corte escolhe como usar (`Clip.facecam_layout`). Com gameplay de fundo, é o que aparece nos blocos
"quem fala" (e no alto da tela dividida da gameplay).
"""

# none: vídeo original (layout do job); dividida: webcam em cima e o vídeo embaixo; camera: só a webcam.
LAYOUTS = ("none", "dividida", "camera")
LAYOUT_LABELS = {
    "none": "Vídeo original",
    "dividida": "Webcam em cima, vídeo embaixo",
    "camera": "Só a webcam",
}
DEFAULT_LAYOUT = "dividida"

CAM_SHARE = 0.4  # na tela dividida, a parte de cima (webcam) ocupa 40% da altura
MIN_SIZE = 0.03  # área menor que 3% do quadro não dá para ampliar


def validate(rect: dict | None) -> dict | None:
    """Normaliza {"x", "y", "w", "h"} (frações do quadro). None = sem recorte."""
    if not rect:
        return None
    try:
        x, y, w, h = (float(rect[k]) for k in ("x", "y", "w", "h"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Área da webcam inválida") from exc
    x, y = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
    w, h = min(w, 1.0 - x), min(h, 1.0 - y)
    if w < MIN_SIZE or h < MIN_SIZE:
        raise ValueError("A área da webcam ficou pequena demais; marque um retângulo maior")
    return {"x": round(x, 4), "y": round(y, 4), "w": round(w, 4), "h": round(h, 4)}


def crop_filter(rect: dict) -> str:
    """Filtro do FFmpeg que recorta a área (em frações do quadro), terminando em vírgula para encadear."""
    return f"crop=w=iw*{rect['w']:.4f}:h=ih*{rect['h']:.4f}:x=iw*{rect['x']:.4f}:y=ih*{rect['y']:.4f},"
