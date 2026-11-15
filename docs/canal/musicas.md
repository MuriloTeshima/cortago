# Músicas de fundo

Catálogo das faixas em `data/music/` (a pasta não vai pro git por causa do tamanho, mas este catálogo vai).
Se perder a pasta, dá pra baixar tudo de novo pela lista abaixo.

- **Fonte:** Biblioteca de áudio do YouTube (YouTube Studio → Biblioteca de áudio)
- **Licença:** Licença da Biblioteca de áudio do YouTube, **atribuição não necessária** em todas
- **Termos da Biblioteca de áudio:** aceitos em 15/11/2026, ao baixar
- **Baixadas em:** 15/11/2026

O prefixo do arquivo indica o clima. A ideia é, no futuro, o Claude escolher a música pelo clima do corte.

| Arquivo | Faixa | Artista | Gênero / clima (biblioteca) | Duração |
| --- | --- | --- | --- | --- |
| `trap_GTA_Type_Beat.mp3` | GTA Type Beat | Dyalla | Hip-Hop e rap / Vibrante | 2:34 |
| `trap_Broken_Glass.mp3` | Broken Glass | Dyalla | Hip-Hop e rap / Dramático | 2:43 |
| `trap_Alias.mp3` | Alias | Anno Domini Beats | Hip-Hop e rap / Sombrio | 2:34 |
| `trap_Mirror_Mirror.mp3` | Mirror Mirror | Anno Domini Beats | Hip-Hop e rap / Dramático | 2:28 |
| `neon_My_Synth_Bae.mp3` | My Synth Bae | The Soundlings | Dance e eletrônica / Vibrante | 2:20 |
| `neon_Flicker_In_The_Night.mp3` | Flicker In The Night | Dyalla | Dance e eletrônica / Dramático | 2:12 |
| `suspense_Conspiracy_Theory.mp3` | Conspiracy Theory | Rod Kim | Dance e eletrônica / Dramático | 1:36 |
| `suspense_Stake_Out.mp3` | Stake Out | Alex Jones / Xander Jones | Dance e eletrônica / Dramático | 3:04 |
| `suspense_Majestic-12.mp3` | Majestic-12 | Alex Jones / Xander Jones | Dance e eletrônica / Dramático | 3:17 |
| `hype_Final_Boss_Battle.mp3` | Final Boss Battle | Rod Kim | Dance e eletrônica / Dramático | 1:41 |
| `hype_Boomin.mp3` | Boomin' | Dan "Lebo" Lebowitz, Tone Seeker | Dance e eletrônica / Vibrante | 2:32 |
| `neutro_Legend.mp3` | Legend | Anno Domini Beats | Hip-Hop e rap / Calmo | 2:58 |

## Como adicionar faixas

1. Biblioteca de áudio → filtrar por **"Atribuição não é necessária"**, gênero e clima.
2. Evitar faixas com "feat." no nome: costumam ter vocal, que briga com a fala do corte.
3. Baixar, renomear como `clima_Nome_Da_Faixa.mp3` e colocar em `data/music/`.
4. Se a faixa **exigir atribuição**, criar `clima_Nome_Da_Faixa.txt` com o texto de crédito da biblioteca.
5. Adicionar a linha nesta tabela.

## Níveis de mixagem

Medidos em 15/11/2026: a música fica em torno de -26 LUFS nas pausas (igual entre faixas diferentes,
graças à normalização) e abaixa ~10 dB quando há fala. Ajuste geral: `CORTAGO_MUSIC_VOLUME` no `.env`
(padrão `0.3`).
