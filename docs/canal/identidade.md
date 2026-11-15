# Identidade

## Nome e @

- **Nome:** Game Cuts
- **@ principal:** `@GameCutsBR`, o mesmo no YouTube, TikTok e Instagram
- **@ reserva:** `@GameCutsOficial`
- **Slogan:** Cortes • Gameplay • Momentos épicos (está no banner)

Disponibilidade conferida no YouTube em 15/11/2026:

| @ | Situação |
| --- | --- |
| @GameCuts | **ocupado** por um canal "Game Cuts" com ~1,1 mil inscritos |
| @GameCutsTV, @GameCutsBrasil | ocupados por canais pequenos (≤ 5 inscritos) |
| **@GameCutsBR**, @GameCutsOficial | livres |

TikTok e Instagram ainda não foram conferidos. Crie o @ nas três plataformas no mesmo dia.

**Pontos fortes do nome:** curto, sonoro e combina com as artes. "Cuts" é entendido pelo público gamer.
**Pontos de atenção:** existe outro canal chamado "Game Cuts" (o dono do @GameCuts, ~1,1 mil inscritos).
O "BR" no @ e o visual synthwave ajudam a diferenciar. Vale olhar o que esse canal publica antes de lançar.

## Descrição do canal (YouTube)

Limite de 1.000 caracteres. As primeiras linhas aparecem na busca, por isso concentram as palavras-chave.

```text
Os momentos mais épicos dos games em poucos segundos. 🎮✂️

No Game Cuts você encontra cortes de lives, gameplays, trailers e notícias do mundo dos games: legendados, rápidos e direto ao ponto. GTA 6, lançamentos, curiosidades, bugs e jogadas absurdas. Se aconteceu nos games, tem corte aqui.

📅 Shorts novos todos os dias
🔔 Inscreva-se e ative o sininho pra não perder nenhum corte

Os créditos dos vídeos originais estão sempre na descrição de cada Short. É criador de conteúdo e quer seus melhores momentos aqui? Manda mensagem!

📩 Contato comercial: [e-mail do canal]
```

## Bio curta (TikTok / Instagram, até 80 caracteres)

```text
Os momentos mais épicos dos games em segundos 🎮✂️ GTA 6 e muito mais
```

## Palavras-chave do canal

`game cuts`, `cortes de games`, `cortes gamer`, `gta 6`, `gta vi`, `games`, `jogos`,
`lançamentos de games`, `notícias de games`, `momentos épicos games`, `shorts games`

## Tom de voz

- Direto: o título promete uma coisa e o corte entrega logo.
- Empolgado sem exagero: nada de "VOCÊ NÃO VAI ACREDITAR!!!" em todo vídeo. Guarde o hype pro que é hype.
- Linguagem de gamer brasileiro ("zerei", "bugou", "clutch"), sem forçar.
- Nunca mentir no título nem na capa. Clickbait enganoso derruba a retenção e pode violar as políticas.

## Visual

Estética **synthwave / anos 80 em Vice City**: pôr do sol, palmeiras, skyline neon, carro clássico.
Paleta extraída das artes (`CorteGamer/backImg.png`):

| Papel | Cor |
| --- | --- |
| Destaque principal (magenta) | `#E33C95` |
| Rosa intenso | `#AE1595` |
| Roxo | `#7E34A1` |
| Roxo escuro (fundos) | `#300854` |
| Quase preto | `#140320` |
| Creme (sol, detalhes) | `#F6D4B7` |
| Texto do logo | branco `#FFFFFF` com contorno preto |

As legendas dos Shorts seguem a marca: a palavra sendo falada em magenta `#E33C95` e o gancho numa caixa
roxa `#300854`, com texto branco. As cores ficam em `src/cortago/subtitles.py` (`BRAND_HIGHLIGHT` e `BRAND_HOOK_BOX`).

### Arquivos das artes (`CorteGamer/`)

| Arquivo | Tamanho | Uso | Situação |
| --- | --- | --- | --- |
| `profileImg.png` | 1254 × 1254 | foto do canal | ✅ ok (mínimo recomendado: 800 × 800) |
| `backImg.png` | 1983 × 793 | banner (versão 1) | ⚠️ abaixo do mínimo do YouTube (2048 × 1152) e com proporção diferente de 16:9 |
| `backImg2.png` | 1983 × 793 | banner (versão 2, original) | ⚠️ mesmo problema; é a base do banner final |
| **`banner_2560x1440.png`** | 2560 × 1440 | **banner para subir no YouTube** | ✅ gerado a partir do `backImg2.png` |

**Banner:** o YouTube pede 2560 × 1440 px (16:9). Em todos os aparelhos aparece só a **área segura central
de 1546 × 423 px**. Logo, texto e "Inscreva-se" precisam caber nessa faixa, senão são cortados no celular.

O `banner_2560x1440.png` encaixa logo, controle, "Inscreva-se" e slogan nessa área. O resto do quadro
(visível na TV e nas laterais do computador) é um brilho desfocado nas cores da arte. Se a arte mudar,
gere de novo:

```bash
uv run --with pillow --with numpy python tools/make_banner.py CorteGamer/backImg2.png \
  CorteGamer/banner_2560x1440.png --box 260 95 1983 610 --preview /tmp/preview.png
```

`--box` é o retângulo (em pixels da arte original) que precisa aparecer em qualquer aparelho. O `--preview`
desenha a área segura (verde) e a faixa do computador (azul) pra conferir.

**Logo:** o ícone de "play" rosa lembra o logo do YouTube. As diretrizes de marca do YouTube não permitem
usar ou imitar o logo dele na identidade do canal. Vale trocar o ícone por um controle, que já aparece no
banner 2, pra evitar problema.

### Tamanhos de imagem

| Peça | Tamanho | Observação |
| --- | --- | --- |
| Foto do canal (avatar) | 800 × 800 px | aparece em círculo e pequena: precisa ser legível em 98 px |
| Banner | 2560 × 1440 px | mínimo 2048 × 1152; área segura: 1546 × 423 px no centro |
| Marca d'água | 150 × 150 px | opcional, botão de inscrever nos vídeos longos |

Confira os tamanhos na ajuda do YouTube Studio ao enviar. Esta tabela segue a orientação usual do YouTube,
mas não foi conferida na fonte oficial.
