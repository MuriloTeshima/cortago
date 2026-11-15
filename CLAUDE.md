# CortaGo

Ferramenta do canal de YouTube **Corte Gamer** (@CorteGamerTV), de cortes de games em português.
Este repositório centraliza o código **e** as informações do canal (`docs/canal/`).

Pipeline que transforma vídeos longos em Shorts 9:16 legendados. Roda localmente em Mac Apple Silicon.

## Comandos

- `uv sync`: instala dependências
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
- `mlx-whisper` só é importado dentro da função que usa (é dependência só de macOS).
- Segredos ficam em `.env` (fora do git). Nunca commitar chaves.

## Arquitetura

Etapas em `src/cortago/`: `download` → `transcribe` → `highlights` (Claude) → `subtitles` → `render`.
`pipeline` orquestra e grava o estado em `db` (SQLite, fonte única de verdade). `cli` roda síncrono;
`web` (FastAPI + Jinja + HTMX, sem build de frontend) enfileira no `worker` (uma tarefa por vez).
Arquivos de cada job em `data/jobs/<id>/` (`source.*`, `transcript.json`, `clips/clip_NN.{mp4,ass,txt}`).

- Testes usam banco em memória e `tmp_path` (fixture em `tests/conftest.py`); na web, `worker` é trocado por fakes.
- IDs usam AUTOINCREMENT: não reaproveitar IDs evita que o navegador mostre vídeo antigo do cache.

## Documentação do canal (`docs/canal/`)

- `docs/canal/README.md` é o índice. Decisões do canal (nome, regras, estratégia) vão em `docs/canal/decisoes.md`
  com data, motivo e alternativas descartadas.
- Números externos (requisitos do YouTube, cotas) sempre com a data em que foram conferidos e a fonte.
- Nada de credenciais, códigos de recuperação ou dados pessoais de terceiros nos docs (só links para onde estão guardados).
- Mudou a biblioteca de músicas? Atualize `docs/canal/musicas.md`.
