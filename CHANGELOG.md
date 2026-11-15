# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased]

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
