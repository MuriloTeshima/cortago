# CortaGo

Transforma um vídeo longo em Shorts 9:16 legendados, rodando localmente no Mac (Apple Silicon).

```text
URL/arquivo → yt-dlp → mlx-whisper (timestamps por palavra) → Claude escolhe os cortes
            → legendas .ass animadas → FFmpeg (9:16, encoder de hardware) → clips/*.mp4 + *.txt
```

## Setup

```bash
brew install uv yt-dlp ffmpeg
uv sync
cp .env.example .env   # coloque sua ANTHROPIC_API_KEY
```

## Uso

```bash
uv run cortago run "https://www.youtube.com/watch?v=..." -n 5
uv run cortago run ~/Downloads/live.mp4 --layout crop --lang pt
```

Saída em `data/jobs/<id>/clips/`: um `.mp4` por corte e um `.txt` com título, descrição, créditos e hashtags.

Cada etapa fica salva em cache (`source.mp4`, `transcript.json`, `clips.json`). Rodar de novo só re-renderiza.
Use `--reselect` pra pedir uma nova seleção ao Claude, ou edite `clips.json` à mão pra ajustar início/fim.

| Opção | Padrão | Descrição |
| --- | --- | --- |
| `-n/--clips` | 5 | máximo de cortes |
| `--layout` | `blur` | `blur`: vídeo inteiro com fundo desfocado (bom pra gameplay). `crop`: corta o centro (bom pra facecam) |
| `--lang` | auto | idioma do áudio |
| `--min/--max` | 20/60 | duração dos cortes em segundos |

## Módulos

- `download.py`: yt-dlp ou arquivo local
- `transcribe.py`: mlx-whisper large-v3-turbo
- `highlights.py`: prompt + structured output do Claude, ajuste dos cortes às bordas das palavras
- `subtitles.py`: legendas estilo Shorts (3 palavras, palavra atual em amarelo, gancho no topo)
- `render.py`: filtros FFmpeg dos layouts
