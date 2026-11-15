"""Adapta uma arte de banner para o formato do YouTube (2560 × 1440, conteúdo na área segura).

Uso: uv run --with pillow --with numpy python tools/make_banner.py ENTRADA SAIDA --box X0 Y0 X1 Y1 [--preview ARQ]

--box é o retângulo, em pixels da arte original, com tudo que precisa aparecer em qualquer aparelho
(logo, textos, botão). Ele é encaixado na área segura central de 1546 × 423 px. O resto do quadro
é preenchido estendendo as bordas da arte (sem repetir o logo) com desfoque.
"""

import argparse

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 2560, 1440
SAFE_W, SAFE_H = 1546, 423  # visível em todos os aparelhos
DESKTOP_H = 423  # no computador aparece a largura toda, nessa altura
MARGIN = 0.97  # folga dentro da área segura
BG_BLUR = 110
BG_EDGE_COLOR = (20, 3, 32)  # #140320, quase preto da paleta: o fundo escurece em direção às bordas do quadro


def _feather_mask(size: tuple[int, int], left: int, top: int, right: int, bottom: int) -> Image.Image:
    """Máscara com rampa linear em cada lado (px de transição por lado)."""
    w, h = size
    xs, ys = np.arange(w, dtype=float), np.arange(h, dtype=float)
    ramp_x = np.minimum(np.clip((xs + 1) / max(left, 1), 0, 1), np.clip((w - xs) / max(right, 1), 0, 1))
    ramp_y = np.minimum(np.clip((ys + 1) / max(top, 1), 0, 1), np.clip((h - ys) / max(bottom, 1), 0, 1))
    return Image.fromarray((np.minimum.outer(ramp_y, ramp_x) * 255).astype(np.uint8), "L")


def _vignette(img: Image.Image, strength: float = 0.85) -> Image.Image:
    """Escurece em direção às bordas do quadro, pro fundo ler como luz suave e não como faixas."""
    xs = np.abs(np.linspace(-1, 1, img.width))
    ys = np.abs(np.linspace(-1, 1, img.height))
    d = np.clip(np.maximum.outer(ys * 1.15, xs) ** 1.6, 0, 1)[..., None] * strength
    arr = np.asarray(img, dtype=float) * (1 - d) + np.array(BG_EDGE_COLOR, dtype=float) * d
    return Image.fromarray(arr.astype(np.uint8))


def build(src: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    x0, y0, x1, y1 = box
    scale = min(SAFE_W * MARGIN / (x1 - x0), SAFE_H * MARGIN / (y1 - y0))

    # Frente: a arte nítida, com o centro do conteúdo no centro do quadro.
    fg = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    cx, cy = (x0 + x1) / 2 * scale, (y0 + y1) / 2 * scale
    ox, oy = round(W / 2 - cx), round(H / 2 - cy)

    # Fundo: estende os pixels da borda da arte até preencher o quadro e desfoca. Continua o céu,
    # a água e as laterais sem duplicar o logo (que fica no meio, longe das bordas).
    pad = (
        (max(oy, 0), max(H - oy - fg.height, 0)),
        (max(ox, 0), max(W - ox - fg.width, 0)),
        (0, 0),
    )
    bg = Image.fromarray(np.pad(np.asarray(fg), pad, mode="edge"))
    bg = bg.crop((max(-ox, 0), max(-oy, 0), max(-ox, 0) + W, max(-oy, 0) + H))
    bg = _vignette(bg.filter(ImageFilter.GaussianBlur(BG_BLUR)))

    # Transição larga onde a arte só tem cenário; estreita onde o conteúdo encosta na borda.
    room = (x0 * scale, y0 * scale, fg.width - x1 * scale, fg.height - y1 * scale)  # folga em cada lado
    widths = [int(max(min(r * 0.8, 260), 14)) for r in room]
    mask = _feather_mask(fg.size, *widths)

    out = bg.copy()
    out.paste(fg, (ox, oy), mask)
    return out


def preview(img: Image.Image) -> Image.Image:
    p = img.copy()
    d = ImageDraw.Draw(p)
    sx, sy = (W - SAFE_W) // 2, (H - SAFE_H) // 2
    d.rectangle([sx, sy, sx + SAFE_W, sy + SAFE_H], outline=(0, 255, 0), width=6)
    d.rectangle([0, (H - DESKTOP_H) // 2, W - 1, (H + DESKTOP_H) // 2], outline=(0, 200, 255), width=4)
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada")
    ap.add_argument("saida")
    ap.add_argument("--box", type=int, nargs=4, required=True)
    ap.add_argument("--preview")
    a = ap.parse_args()
    result = build(Image.open(a.entrada).convert("RGB"), tuple(a.box))
    result.save(a.saida, optimize=True)
    if a.preview:
        preview(result).save(a.preview)
    print(f"{a.saida}: {result.width}x{result.height}")
