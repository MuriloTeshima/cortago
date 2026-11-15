# CortaGo

Transforma um vídeo longo em Shorts 9:16 legendados, rodando localmente no Mac (Apple Silicon).

Ferramenta do canal **Game Cuts** (@GameCutsBR). Tudo sobre o canal (identidade, criação, políticas,
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

### Música de fundo

Coloque faixas livres de direitos em `data/music/` (mp3, m4a, wav, ogg, flac). Uma boa fonte é a
**Biblioteca de áudio do YouTube** (YouTube Studio → Biblioteca de áudio). Cada corte recebe uma faixa
sorteada, começando num ponto aleatório, com fade e ducking: a música abaixa ~10 dB quando alguém fala e
volta nas pausas. Dá pra trocar a faixa ou tirar a música na edição do corte.

Se a faixa exige atribuição, crie um `.txt` com o mesmo nome (`Faixa.mp3` → `Faixa.txt`) contendo o
crédito; ele entra automaticamente na descrição.

O volume é automático e relativo ao vídeo: o CortaGo mede o áudio de cada trecho e deixa a música
`CORTAGO_MUSIC_GAP_DB` dB abaixo dele (padrão `12`), então vídeos gravados baixo ganham música baixa.
Se ainda assim a música sobressair num corte, use os botões **− / +** ao lado do nome da faixa
(passos de 25%) ou o controle "Volume da música" na edição (0–150%, 100% = automático).

> Não use música comercial: gera claim no Content ID e pode desmonetizar ou derrubar o vídeo.

### Terminal

```bash
uv run cortago run "https://www.youtube.com/watch?v=..." -n 5
uv run cortago run ~/Downloads/live.mp4 --layout crop --lang pt --no-music
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
- `music.py`: biblioteca de músicas de fundo (sorteio, créditos)
- `download.py`: yt-dlp ou arquivo local
- `transcribe.py`: mlx-whisper large-v3-turbo
- `highlights.py`: prompt + structured output do Claude, ajuste dos cortes às bordas das palavras
- `subtitles.py`: legendas estilo Shorts (3 palavras, palavra atual em amarelo, gancho no topo)
- `render.py`: filtros FFmpeg dos layouts e mixagem da música (loudnorm + sidechain ducking)
