# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Adicionado
- Música de fundo: cada corte recebe uma faixa sorteada da biblioteca `data/music/`, normalizada,
  com fade e ducking (abaixa ~10 dB durante a fala, igual pra vídeos gravados alto ou baixo).
- Trocar ou remover a música na edição do corte; opção "Música de fundo" ao criar o job e `--no-music` na CLI.
- Volume da música automático e relativo ao áudio de cada trecho (fica `CORTAGO_MUSIC_GAP_DB` dB abaixo),
  pra música não sobressair em vídeos gravados baixo.
- Editor de volume da música por corte: botões − / + no card e controle de 0–150% na edição.
- Crédito da música (arquivo `.txt` ao lado da faixa) incluído automaticamente na descrição.
- Migração automática do banco para colunas novas (mudanças aditivas).
- `tools/make_banner.py`: adapta uma arte para banner do YouTube (2560 × 1440, conteúdo na área segura).

### Alterado
- Legendas com as cores da marca Game Cuts: palavra falada em magenta (`#E33C95`) e gancho em caixa roxa (`#300854`).

## [0.2.0] - 2026-11-15

### Adicionado
- Interface web (`cortago serve`): enviar vídeos, acompanhar o progresso, assistir, aprovar,
  descartar e editar cortes, baixar o vídeo e copiar o texto pronto pro YouTube.
- Banco SQLite com jobs e cortes, compartilhado entre CLI e interface.
- Fila em segundo plano que retoma o processamento interrompido quando o servidor reinicia.

### Alterado
- A CLI passou a usar o mesmo pipeline e banco da interface. Saída agora em `data/jobs/<id>/clips/`.
- Removida a opção `--reselect` da CLI (use "Escolher de novo" na interface).

## [0.1.0] - 2026-11-14

### Adicionado
- CLI `cortago run` que gera Shorts a partir de URL ou arquivo local.
- Download com yt-dlp e transcrição local com mlx-whisper (timestamps por palavra).
- Seleção de cortes com Claude via structured outputs, ajustada às bordas das palavras.
- Legendas estilo Shorts (palavra atual destacada) e gancho no topo.
- Render 9:16 com FFmpeg nos layouts `blur` e `crop`, usando encoder de hardware.
- Lint (ruff), testes (pytest) e CI no GitHub Actions.

[Unreleased]: https://github.com/MuriloTeshima/cortago/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/MuriloTeshima/cortago/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/MuriloTeshima/cortago/releases/tag/v0.1.0
