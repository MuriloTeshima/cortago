<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.png">
    <img src="docs/assets/logo-light.png" alt="CortaGo" width="420">
  </picture>
</p>

<p align="center">
  <strong>Vídeos longos → Shorts prontos.</strong><br>
  Corta, legenda e coloca música em vídeos de YouTube, Twitch e afins, direto no seu computador.
</p>

<p align="center">
  <a href="https://github.com/MuriloTeshima/cortago/actions/workflows/ci.yml"><img src="https://github.com/MuriloTeshima/cortago/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licença-MIT-FFD400" alt="Licença MIT"></a>
  <img src="https://img.shields.io/badge/python-3.12+-3776AB" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/macOS%20·%20Windows%20·%20Linux-suportados-171920" alt="macOS, Windows e Linux">
</p>

# CortaGo

Você cola o link de um vídeo ou live (ou escolhe um arquivo) e o CortaGo entrega os melhores trechos como
**Shorts 9:16** prontos para postar: legendados palavra por palavra, com gancho na tela e música de fundo.
Tudo roda **localmente** no seu computador. Só a escolha dos cortes usa a API do Claude.

## O que faz

- **Escolhe os melhores momentos.** O vídeo é transcrito localmente com o Whisper e o Claude lê a transcrição
  para escolher os trechos com mais potencial, cada um com título, gancho, descrição e hashtags.
- **Corta no lugar certo.** Início e fim ajustados às bordas das palavras, sem cortar sílabas.
- **Legenda estilo Shorts.** Poucas palavras por vez, a palavra falada destacada e um gancho no topo.
- **Formato vertical.** `blur` (vídeo inteiro com fundo desfocado, ideal para gameplay) ou `crop` (corta o centro, ideal para câmera).
- **Música de fundo.** Sorteada da sua biblioteca, com volume relativo ao vídeo e *ducking* (abaixa quando alguém fala).
- **Revisão na interface web.** Assista, aprove, descarte e ajuste título, gancho, tempos, música e volume, com re-render automático.
- **Pronto para postar.** Painel "Postar no YouTube" com botão de copiar para cada campo do YouTube Studio.
- **Usa o seu hardware.** GPU Apple, NVIDIA, Intel ou AMD quando houver; CPU quando não.

```text
link ou arquivo → download (yt-dlp) → transcrição (Whisper, local) → Claude escolhe os cortes
                → legendas animadas → FFmpeg (9:16 + música) → revisão na interface → postar
```

## Requisitos

- **uv** (gerenciador do Python) e **FFmpeg com libass** (para as legendas). O resto o `uv sync` instala.
- Uma **chave da API do Claude** ([console.anthropic.com](https://console.anthropic.com)). A escolha dos cortes
  custa centavos de dólar por hora de vídeo.

## Instalação

#### macOS

```bash
brew install uv ffmpeg
```

#### Windows (PowerShell)

```powershell
winget install --id=astral-sh.uv -e
winget install --id=Gyan.FFmpeg -e   # build completa: inclui libass e encoders NVIDIA/Intel/AMD
```

Feche e abra o terminal depois de instalar, para o PATH ser atualizado.

#### Linux (Debian/Ubuntu)

```bash
sudo apt install ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Em todos

```bash
git clone https://github.com/MuriloTeshima/cortago.git
cd cortago
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

1. Cole o link (ou o caminho de um arquivo), escolha quantos cortes, layout, idioma e duração.
2. Acompanhe o processamento: download, transcrição, escolha dos cortes e render.
3. Revise cada corte: assista, aprove ou descarte e edite título, gancho, descrição, hashtags, início/fim,
   música e volume. O vídeo é renderizado de novo sozinho quando precisa. "Escolher de novo" pede outra seleção ao Claude.
4. Para postar, abra **"Postar no YouTube"** no card do corte: passo a passo do YouTube Studio, botão de copiar
   para cada campo (título, descrição com créditos e hashtags, tags), contadores com os limites do YouTube e
   as opções que você marca à mão (categoria, idioma, "não é para crianças").

### Terminal

```bash
uv run cortago run "https://www.youtube.com/watch?v=..." -n 5
uv run cortago run ~/Downloads/live.mp4 --layout crop --lang pt --no-music
```

| Opção | Padrão | Descrição |
| --- | --- | --- |
| `-n/--clips` | 5 | máximo de cortes |
| `--layout` | `blur` | `blur`: vídeo inteiro com fundo desfocado. `crop`: corta o centro |
| `--lang` | auto | idioma do áudio |
| `--min/--max` | 20/60 | duração dos cortes em segundos |
| `--music/--no-music` | com música | música de fundo sorteada da biblioteca |

Jobs criados pelo terminal também aparecem na interface.

### Comandos

| Comando | Para quê |
| --- | --- |
| `uv run cortago serve` | interface web |
| `uv run cortago run <link\|arquivo>` | processa um vídeo direto no terminal |
| `uv run cortago doctor` | diagnóstico: sistema, FFmpeg, encoder, transcrição, chave da API, músicas |

### Música de fundo

Coloque faixas livres de direitos em `data/music/` (mp3, m4a, wav, ogg, flac) ou aponte outra pasta em
`CORTAGO_MUSIC_DIR`. Uma boa fonte é a **Biblioteca de áudio do YouTube** (YouTube Studio → Biblioteca de áudio).

- Cada corte recebe uma faixa sorteada, começando num ponto aleatório, com fade de entrada e saída.
- O volume é relativo ao vídeo: o CortaGo mede o áudio de cada trecho e deixa a música
  `CORTAGO_MUSIC_GAP_DB` dB abaixo (padrão `12`). Quando alguém fala, ela abaixa mais ~10 dB (*ducking*).
- Se ainda assim sobressair, use **− / +** ao lado do nome da faixa (passos de 25%) ou o controle
  "Volume da música" na edição (0–150%, 100% = automático).
- Na edição, ao escolher outra faixa ela já toca como prévia. Todas as faixas podem ser ouvidas em `/musicas`.
- Faixa que exige atribuição: crie um `.txt` com o mesmo nome (`Faixa.mp3` → `Faixa.txt`) com o crédito.
  Ele entra automaticamente na descrição.

> Não use música comercial: gera claim no Content ID e pode desmonetizar ou derrubar o vídeo.

### Efeitos de retenção

Pensados para os primeiros segundos e o ritmo do Short. Cada corte liga ou desliga na edição
(seção "Efeitos"); os padrões para cortes novos vêm do `.env`.

| Efeito | O que faz | Variável (padrão) |
| --- | --- | --- |
| Cortar silêncios | remove pausas longas **sem fala e sem som** (som de jogo e trailer nunca são cortados) e começa já na primeira palavra | `CORTAGO_FX_JUMP_CUTS` (`1`) |
| Zoom de entrada | o vídeo começa ampliado e volta ao normal em 0,6 s | `CORTAGO_FX_INTRO_ZOOM` (`suave`; ou `none`, `forte`) |
| Gancho animado | o texto do topo entra "saltando" | `CORTAGO_FX_HOOK_ANIM` (`1`) |
| Som do gancho | *whoosh*, *pop* ou *impact* gerados pela própria ferramenta, com prévia na edição | `CORTAGO_FX_HOOK_SFX` (`whoosh`) |
| Barra de progresso | linha fina no topo, na cor de destaque | `CORTAGO_FX_PROGRESS_BAR` (`1`) |

### Personalizar para o seu canal

A ferramenta é genérica. Tudo que é do canal fica no `.env`:

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `CORTAGO_CHANNEL_CONTEXT` | `um canal brasileiro de cortes de games no YouTube Shorts` | quem é o canal, em uma frase; orienta o Claude na escolha dos cortes |
| `CORTAGO_HIGHLIGHT_COLOR` | `#FFE500` | cor da palavra sendo falada na legenda |
| `CORTAGO_HOOK_BOX_COLOR` | `#000000` | cor da caixa do gancho no topo |
| `CORTAGO_MUSIC_DIR` | `data/music` | pasta com as músicas de fundo |
| `CORTAGO_MUSIC_GAP_DB` | `12` | quantos dB a música fica abaixo do áudio do vídeo |
| `CORTAGO_YT_CATEGORY` | `Jogos` | categoria indicada no painel "Postar no YouTube" |
| `CORTAGO_YT_LANGUAGE` | `Português (Brasil)` | idioma indicado no painel |
| `CORTAGO_YT_EXTRA_TAGS` | (vazio) | tags somadas às de cada corte, separadas por vírgula |
| `CORTAGO_CLAUDE_MODEL` | `claude-opus-5-5` | modelo do Claude usado para escolher os cortes |

### Onde ficam os dados

Tudo em `data/` (fora do git): o banco `cortago.db` e uma pasta por job em `data/jobs/<id>/` com
`source.mp4`, `transcript.json` e `clips/` (um `.mp4` e um `.txt` por corte). Etapas já feitas são
reaproveitadas, então rodar de novo só refaz o que mudou.

## Desenvolvimento

```bash
uv run pytest -q                              # testes (não usam rede, GPU nem a API do Claude)
uv run ruff check . && uv run ruff format .   # lint e formatação
uv run cortago serve --reload                 # interface recarregando ao editar o código
```

A CI roda lint e testes em Ubuntu, Windows e macOS a cada push e PR. Convenções do projeto (fluxo de git,
commits, changelog) estão em [CLAUDE.md](CLAUDE.md) e o histórico de versões em [CHANGELOG.md](CHANGELOG.md).

### Módulos (`src/cortago/`)

| Módulo | Responsabilidade |
| --- | --- |
| `pipeline.py` | orquestra as etapas e grava o progresso no banco |
| `download.py` | yt-dlp (como biblioteca) ou arquivo local |
| `hardware.py` | detecta o computador e escolhe transcrição e encoder |
| `transcribe.py` | Whisper large-v3-turbo via MLX (Mac com chip Apple) ou faster-whisper |
| `highlights.py` | prompt e structured output do Claude; ajuste dos cortes às bordas das palavras |
| `subtitles.py` | legendas estilo Shorts (`.ass`) e gancho no topo |
| `render.py` | layouts 9:16 no FFmpeg e mixagem da música (loudnorm + sidechain ducking) |
| `effects.py` | efeitos de retenção: cortes de silêncio, zoom, gancho animado, sons, barra |
| `music.py` | biblioteca de músicas (sorteio, créditos) |
| `post_info.py` | campos prontos para o YouTube (título, descrição, tags) |
| `db.py` | modelos `Job` e `Clip` (SQLite via SQLModel) e migração automática |
| `worker.py` | fila em segundo plano da interface (uma tarefa por vez) |
| `web/` | FastAPI + templates Jinja/HTMX, sem build de frontend |
| `cli.py` | comandos `serve`, `run` e `doctor` |

## Licença

[MIT](LICENSE).
