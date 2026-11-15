# CortaGo

Transforma um vídeo longo em Shorts 9:16 legendados, rodando localmente no seu computador:
**macOS, Windows ou Linux**. A ferramenta detecta o hardware e usa o melhor caminho disponível.

```text
URL/arquivo → yt-dlp → mlx-whisper (timestamps por palavra) → Claude escolhe os cortes
            → legendas .ass animadas → FFmpeg (9:16, encoder de hardware) → clips/*.mp4 + *.txt
```

## Instalação

Precisa de **uv** (gerenciador do Python) e **FFmpeg com libass** (para as legendas). O resto
(yt-dlp, Whisper etc.) o `uv sync` instala.

**macOS**

```bash
brew install uv ffmpeg
```

**Windows** (PowerShell)

```powershell
winget install --id=astral-sh.uv -e
winget install --id=Gyan.FFmpeg -e   # build completa: inclui libass e encoders NVIDIA/Intel/AMD
```

Feche e abra o terminal depois de instalar, para o PATH ser atualizado.

**Linux** (Debian/Ubuntu)

```bash
sudo apt install ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Em todos**

```bash
uv sync
cp .env.example .env      # no Windows: copy .env.example .env  — e coloque sua ANTHROPIC_API_KEY
uv run cortago doctor     # mostra o que foi detectado e o que está faltando
```

### O que é usado em cada computador

| Computador | Transcrição (Whisper) | Encoder de vídeo |
| --- | --- | --- |
| Mac com chip Apple (M1 ou mais novo) | MLX na GPU Apple | VideoToolbox |
| Placa NVIDIA | faster-whisper na GPU (CUDA) | NVENC |
| Intel / AMD com vídeo integrado | faster-whisper na CPU | Quick Sync / AMF |
| Qualquer outro | faster-whisper na CPU | libx264 |

- **GPU NVIDIA na transcrição** exige CUDA 12 e cuDNN 9 instalados (ver a documentação do faster-whisper).
  Sem eles, a ferramenta avisa e transcreve na CPU automaticamente.
- **Só CPU** funciona, mas é mais lento: a transcrição pode levar perto da duração do vídeo. Num PC
  modesto, `CORTAGO_WHISPER_MODEL=small` acelera bastante com alguma perda de precisão.
- Para forçar algo: `CORTAGO_WHISPER_BACKEND` (`mlx` | `faster-whisper`), `CORTAGO_WHISPER_MODEL`,
  `CORTAGO_VIDEO_ENCODER` (`libx264`, `h264_nvenc`, `h264_videotoolbox`…).

## Uso

### Interface web

```bash
uv run cortago serve        # abre em http://127.0.0.1:8000
```

Cole a URL, acompanhe o processamento e revise os cortes: assistir, aprovar/descartar, editar título,
gancho, descrição, hashtags e início/fim (re-renderiza sozinho), baixar o `.mp4` e copiar o texto pronto
pro YouTube. "Escolher de novo" pede uma nova seleção ao Claude.

Na hora de postar, abra **"Postar no YouTube"** no card do corte. Ele mostra o passo a passo do YouTube
Studio com um botão de copiar para cada campo (título, descrição com créditos e hashtags, tags), contadores
com os limites do YouTube e as opções que você marca à mão (categoria, idioma, "não é para crianças").

### Música de fundo

Coloque faixas livres de direitos em `data/music/` (mp3, m4a, wav, ogg, flac). Uma boa fonte é a
**Biblioteca de áudio do YouTube** (YouTube Studio → Biblioteca de áudio). Cada corte recebe uma faixa
sorteada, começando num ponto aleatório, com fade e ducking: a música abaixa ~10 dB quando alguém fala e
volta nas pausas. Dá pra trocar a faixa ou tirar a música na edição do corte; ao escolher outra faixa, ela já toca
como prévia. Todas as faixas podem ser ouvidas em `/musicas` (link "N faixas na biblioteca" na página inicial).

Se a faixa exige atribuição, crie um `.txt` com o mesmo nome (`Faixa.mp3` → `Faixa.txt`) contendo o
crédito; ele entra automaticamente na descrição.

O volume é automático e relativo ao vídeo: o CortaGo mede o áudio de cada trecho e deixa a música
`CORTAGO_MUSIC_GAP_DB` dB abaixo dele (padrão `12`), então vídeos gravados baixo ganham música baixa.
Se ainda assim a música sobressair num corte, use os botões **− / +** ao lado do nome da faixa
(passos de 25%) ou o controle "Volume da música" na edição (0–150%, 100% = automático).

> Não use música comercial: gera claim no Content ID e pode desmonetizar ou derrubar o vídeo.

### Personalizar para o seu canal

A ferramenta é genérica. Tudo que é do canal fica no `.env`:

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `CORTAGO_CHANNEL_CONTEXT` | `um canal brasileiro de cortes de games no YouTube Shorts` | quem é o canal, em uma frase; orienta o Claude na escolha dos cortes |
| `CORTAGO_HIGHLIGHT_COLOR` | `#FFE500` | cor da palavra sendo falada na legenda |
| `CORTAGO_HOOK_BOX_COLOR` | `#000000` | cor da caixa do gancho no topo |
| `CORTAGO_MUSIC_DIR` | `data/music` | pasta com as músicas de fundo do canal |
| `CORTAGO_MUSIC_GAP_DB` | `12` | quantos dB a música fica abaixo do áudio do vídeo |
| `CORTAGO_YT_CATEGORY` | `Jogos` | categoria indicada no painel "Postar no YouTube" |
| `CORTAGO_YT_LANGUAGE` | `Português (Brasil)` | idioma indicado no painel |
| `CORTAGO_YT_EXTRA_TAGS` | (vazio) | tags somadas às de cada corte, separadas por vírgula |

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
- `hardware.py`: detecta o computador e escolhe transcrição e encoder
- `download.py`: yt-dlp (biblioteca) ou arquivo local
- `transcribe.py`: Whisper large-v3-turbo via MLX (Mac Apple) ou faster-whisper (demais)
- `highlights.py`: prompt + structured output do Claude, ajuste dos cortes às bordas das palavras
- `subtitles.py`: legendas estilo Shorts (3 palavras, palavra atual em amarelo, gancho no topo)
- `render.py`: filtros FFmpeg dos layouts e mixagem da música (loudnorm + sidechain ducking)

## Licença

[MIT](LICENSE).
