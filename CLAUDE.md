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
- IDs usam AUTOINCREMENT: não reaproveitar IDs evita que o navegador mostre vídeo antigo do cache.
