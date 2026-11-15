# CortaGo

Pipeline que transforma vídeos longos em Shorts 9:16 legendados. Roda localmente em Mac Apple Silicon.

## Comandos

- `uv sync`: instala dependências
- `uv run cortago run <url|arquivo>`: roda o pipeline
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

`src/cortago/`: `download` → `transcribe` → `highlights` (Claude) → `subtitles` → `render`, orquestrados por `cli`.
Cada job fica em `data/jobs/<id>/` com cache por etapa (`source.mp4`, `transcript.json`, `clips.json`, `clips/`).
