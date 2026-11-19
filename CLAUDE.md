# CortaGo

Ferramenta **genérica**: não depende de nenhum canal específico. Nada de nome, marca, cores ou regras de
um canal no código ou nos docs deste repositório. O que é de cada canal entra por variáveis no `.env`
(`CORTAGO_CHANNEL_CONTEXT`, `CORTAGO_HIGHLIGHT_COLOR`, `CORTAGO_HOOK_BOX_COLOR`, `CORTAGO_MUSIC_DIR`…).

Pipeline que transforma vídeos longos em Shorts 9:16 legendados. Roda localmente em macOS, Windows e Linux;
`hardware.py` detecta o computador (MLX/VideoToolbox no Mac Apple, CUDA/NVENC com NVIDIA, CPU no resto).

## Comandos

- `uv sync`: instala dependências
- `uv run cortago doctor`: mostra hardware detectado e o que falta
- `uv run cortago serve [--reload]`: interface web em http://127.0.0.1:8000
- `uv run cortago run <url|arquivo>`: roda o pipeline no terminal
- `uv run pytest -q`: testes
- `uv run ruff check . && uv run ruff format .`: lint e formatação

## Convenções

- Fluxo de git: `main` é protegida na prática. Todo trabalho em branch (`feat/...`, `fix/...`, `chore/...`, `docs/...`) e entra por PR com CI verde.
- Commits no padrão Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
- Toda mudança visível ao usuário entra no `CHANGELOG.md` em `[Unreleased]`. Releases usam SemVer com tag `vX.Y.Z`.
- Textos de interface, prompts e mensagens da CLI em português do Brasil.
- Lógica nova vem com teste em `tests/`. Testes não podem depender de rede, da API do Claude nem de MLX (CI roda em Linux).
- `mlx-whisper` só é importado dentro da função que usa (dependência só de Mac com chip Apple).
- Multiplataforma: sempre `encoding="utf-8"` ao ler/gravar texto e nos `subprocess` com `text=True`
  (o padrão do Windows é cp1252). O faster-whisper recebe o áudio já decodificado pelo FFmpeg (`load_audio`).
- A CI roda em Ubuntu, Windows e macOS. Testes não podem depender de GPU, FFmpeg ou do `.env` local.
- Segredos ficam em `.env` (fora do git). Nunca commitar chaves.

## Arquitetura

Etapas em `src/cortago/`: `download` → `transcribe` → `highlights` (Claude) → `subtitles` → `render`.
`pipeline` orquestra e grava o estado em `db` (SQLite, fonte única de verdade). `cli` roda síncrono;
`web` (FastAPI + Jinja + HTMX, sem build de frontend) enfileira no `worker` (uma tarefa por vez).
Regras de edição de um corte ficam em `editing.py` (valida, grava e devolve `EditResult(clip, rerender)`), sem HTTP:
rotas, CLI e futuras telas (timeline) usam o mesmo módulo. `web/app.py` só monta a aplicação; rotas em
`web/routes/` (`videos`, `clips`, `library`, `media`) e o compartilhado em `web/common.py`.
Editor: cada aba é um parcial em `templates/editor/`; ao salvar, a resposta traz a aba e, via `hx-swap-oob`,
o player e o painel de postagem (`editor/_oob.html`).
Arquivos de cada job em `data/jobs/<id>/` (`source.*`, `transcript.json`, `clips/clip_NN.{mp4,ass,txt}`).

- Testes usam banco em memória e `tmp_path` (fixture em `tests/conftest.py`); na web, `worker` é trocado por fakes.
- Colunas novas: `db.migrate()` adiciona automaticamente ao abrir o banco (só mudanças aditivas, com
  default fixo). Renomear/remover coluna exige adotar Alembic. Faça backup de `data/cortago.db` antes de testar.
- Música: `Clip.music_track` é `None` (sortear no próximo render), `""` (sem música) ou nome do arquivo em `MUSIC_DIR`.
  No formulário, "sem música" é o valor `__none__` porque o FastAPI trata campo vazio como ausente.
- Campos de postagem (título, descrição, tags) saem de `post_info.build()`, usado pelo painel "Postar no
  YouTube" e pelo `.txt` de cada corte. Limites do YouTube em `post_info.TITLE_LIMIT` etc.
- Volume da música: `render.auto_music_volume()` usa o loudness medido do trecho (`measure_loudness`, ebur128)
  menos `MUSIC_GAP_DB`, limitado a -40…-20 LUFS, vezes `Clip.music_level` (% manual, 100 = automático).
- Efeitos (`effects.py`): campos por corte em `Clip` (padrão do `.env` só em cortes novos; antigos ficam sem
  efeitos). Cortes de silêncio usam palavras **e** `render.detect_quiet` (silencedetect relativo ao loudness do
  corte): nunca cortar só por falta de palavras, senão some o som do jogo/trailer. Com cortes, os tempos das
  legendas passam por `effects.remap`. No formulário, a seção usa `effects_form` porque checkbox desmarcado não é enviado.
- Trecho do vídeo: `Job.range_start/range_end` estão no relógio do **vídeo original**; `Job.source_offset` é onde o
  arquivo baixado começa (> 0 quando só o trecho foi baixado). Transcrição e cortes ficam no relógio do **arquivo**
  (`Job.window()` converte). A interface mostra e recebe tempos do original (soma/subtrai `source_offset`).
- Timeline: `Clip.edit` (JSON) é o documento de edição não destrutivo: `segments` (trechos manuais, tempo do arquivo,
  substituem o corte automático) e `words` (correções de legenda pela chave `timeline.word_key`, início com 2 casas).
  `pipeline.effective_segments` decide manual > automático > nenhum. Frontend em `static/timeline.js` (JS puro, sem
  build; prévia toca `/media/<job>/origem` pulando os trechos removidos).
- Gameplay de fundo (`gameplay.py`): `Job.gameplay_source/gameplay_file` (arquivo compartilhado em `data/gameplay/`),
  `Clip.gameplay_mode` (`none|alternar|dividida`), `Clip.gameplay_hints` (indicação do Claude) e `Clip.edit["gameplay"]`
  (ajuste manual). Prioridade manual > Claude > alternância automática. A imagem só troca nas bordas de
  `gameplay.blocks` (frases) e o gancho fica em quem fala; `gameplay.to_output` passa os tempos pelos cortes de silêncio.
  A voz é sempre do vídeo principal.
- IDs usam AUTOINCREMENT: não reaproveitar IDs evita que o navegador mostre vídeo antigo do cache.
