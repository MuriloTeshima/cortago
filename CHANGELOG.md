# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Adicionado
- Processar só um trecho do vídeo: campos "começa em / termina em" na criação (e `--inicio/--fim` na CLI),
  aceitando `1:20:00`, `80:00`, `4800` ou `1h20m`. Em links, só o trecho é baixado quando o site permite;
  senão, baixa inteiro e transcreve só o trecho.
- Créditos com o link no instante do corte no vídeo original (YouTube e Twitch).

### Alterado
- Tempos dos cortes (no card e na edição) aparecem no relógio do vídeo original, mesmo quando só um trecho foi baixado.

## [0.4.0] - 2026-11-17

### Adicionado
- **Multiplataforma (macOS, Windows, Linux):** a ferramenta detecta o computador e escolhe sozinha a
  transcrição (MLX no Mac com chip Apple, faster-whisper em GPU NVIDIA ou CPU) e o encoder de vídeo
  (VideoToolbox, NVENC, Quick Sync, AMF ou libx264). Instruções de instalação para os três sistemas.
- `cortago doctor`: mostra o hardware detectado e o que está faltando (FFmpeg, libass, chave da API).
- **Efeitos de retenção**, ligados por corte na edição (seção "Efeitos") e com padrões no `.env`:
  cortes de silêncio (só pausas sem fala **e** sem som; som de jogo e trailer são preservados),
  zoom de entrada, gancho animado, som no gancho (whoosh/pop/impact gerados pela ferramenta, com
  prévia) e barra de progresso. O card mostra um resumo dos efeitos ativos.
- **Painel "Postar no YouTube"** em cada corte: passo a passo do YouTube Studio com botão de copiar por campo
  (título, descrição, tags), contadores com os limites do YouTube, as opções a marcar à mão e aviso quando
  os créditos ainda são de arquivo local. Configurável com `CORTAGO_YT_CATEGORY`, `CORTAGO_YT_LANGUAGE` e
  `CORTAGO_YT_EXTRA_TAGS`.
- **Prévia das músicas:** player na edição do corte que toca a faixa escolhida antes de salvar, e página
  `/musicas` com todas as faixas da biblioteca (link na página inicial).
- Limitador no fim da mixagem (teto de -1 dB) para evitar distorção ao somar música e efeitos.
- Identidade visual: logo no cabeçalho da interface e no README (versões para tema claro e escuro),
  favicon e ícones do app.
- Licença MIT. CI rodando em Ubuntu, Windows e macOS.

### Alterado
- O yt-dlp passou a ser usado como biblioteca Python (instalado pelo `uv sync`), não como programa externo.
- `CORTAGO_VIDEO_ENCODER` e `CORTAGO_WHISPER_MODEL` agora são automáticos por padrão.
- O botão "Copiar texto" foi substituído pelo painel "Postar no YouTube". O `.txt` ao lado do vídeo continua igual.

## [0.3.0] - 2026-11-15

### Adicionado
- Música de fundo: cada corte recebe uma faixa sorteada da biblioteca `data/music/`, normalizada,
  com fade e ducking (abaixa ~10 dB durante a fala, igual pra vídeos gravados alto ou baixo).
- Trocar ou remover a música na edição do corte; opção "Música de fundo" ao criar o job e `--no-music` na CLI.
- Volume da música automático e relativo ao áudio de cada trecho (fica `CORTAGO_MUSIC_GAP_DB` dB abaixo),
  pra música não sobressair em vídeos gravados baixo.
- Editor de volume da música por corte: botões − / + no card e controle de 0–150% na edição.
- Crédito da música (arquivo `.txt` ao lado da faixa) incluído automaticamente na descrição.
- Migração automática do banco para colunas novas (mudanças aditivas).
- Personalização por canal via `.env`: `CORTAGO_CHANNEL_CONTEXT` (contexto do canal no prompt do Claude),
  `CORTAGO_HIGHLIGHT_COLOR` e `CORTAGO_HOOK_BOX_COLOR` (cores das legendas).

### Alterado
- O prompt de escolha dos cortes deixou de ser fixo em "canal sobre GTA 6" e usa o contexto configurado
  (padrão: canal de cortes de games em geral).

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

[Unreleased]: https://github.com/MuriloTeshima/cortago/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/MuriloTeshima/cortago/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/MuriloTeshima/cortago/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/MuriloTeshima/cortago/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/MuriloTeshima/cortago/releases/tag/v0.1.0
