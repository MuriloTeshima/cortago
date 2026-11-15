# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased]

## [0.1.0] - 2026-11-14

### Adicionado
- CLI `cortago run` que gera Shorts a partir de URL ou arquivo local.
- Download com yt-dlp e transcrição local com mlx-whisper (timestamps por palavra).
- Seleção de cortes com Claude via structured outputs, ajustada às bordas das palavras.
- Legendas estilo Shorts (palavra atual destacada) e gancho no topo.
- Render 9:16 com FFmpeg nos layouts `blur` e `crop`, usando encoder de hardware.
- Lint (ruff), testes (pytest) e CI no GitHub Actions.
