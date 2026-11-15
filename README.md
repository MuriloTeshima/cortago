# CortaGo

Transforma um vídeo longo em Shorts 9:16 legendados, rodando localmente no Mac (Apple Silicon).

Ferramenta do canal **Corte Gamer** (@CorteGamerTV). Tudo sobre o canal (identidade, criação, políticas,
estratégia e fluxo de produção) está em [docs/canal/](docs/canal/README.md).

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

### Interface web

```bash
uv run cortago serve        # abre em http://127.0.0.1:8000
```

Cole a URL, acompanhe o processamento e revise os cortes: assistir, aprovar/descartar, editar título,
gancho, descrição, hashtags e início/fim (re-renderiza sozinho), baixar o `.mp4` e copiar o texto pronto
pro YouTube. "Escolher de novo" pede uma nova seleção ao Claude.

### Terminal

```bash
uv run cortago run "https://www.youtube.com/watch?v=..." -n 5
uv run cortago run ~/Downloads/live.mp4 --layout crop --lang pt
```

Jobs criados pelo terminal também aparecem na interface.

Os dados ficam em `data/`: o banco `cortago.db` e uma pasta por job em `data/jobs/<id>/` com `source.mp4`,
`transcript.json` e `clips/` (um `.mp4` e um `.txt` por corte). Etapas já feitas são reaproveitadas.

| Opção | Padrão | Descrição |
| --- | --- | --- |
| `-n/--clips` | 5 | máximo de cortes |
| `--layout` | `blur` | `blur`: vídeo inteiro com fundo desfocado (bom pra gameplay). `crop`: corta o centro (bom pra facecam) |
| `--lang` | auto | idioma do áudio |
| `--min/--max` | 20/60 | duração dos cortes em segundos |

## Módulos

- `db.py`: modelos `Job` e `Clip` (SQLite via SQLModel)
- `pipeline.py`: orquestra as etapas e grava o progresso no banco
- `worker.py`: fila em segundo plano da interface web (uma tarefa por vez)
- `web/`: FastAPI + templates Jinja/HTMX
- `download.py`: yt-dlp ou arquivo local
- `transcribe.py`: mlx-whisper large-v3-turbo
- `highlights.py`: prompt + structured output do Claude, ajuste dos cortes às bordas das palavras
- `subtitles.py`: legendas estilo Shorts (3 palavras, palavra atual em amarelo, gancho no topo)
- `render.py`: filtros FFmpeg dos layouts
