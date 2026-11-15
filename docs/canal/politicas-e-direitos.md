# Políticas e direitos

> Isto é um resumo operacional, não aconselhamento jurídico. Em caso de dúvida, consulte as páginas
> oficiais do YouTube (Central de Ajuda → Políticas de monetização de canais / Direitos autorais).

Um canal de cortes corre dois riscos diferentes, que andam separados:

| Risco | O que é | Consequência |
| --- | --- | --- |
| **Direitos autorais / Content ID** | usar vídeo ou música de outra pessoa | claim (a receita vai pro dono), bloqueio do vídeo ou **strike**. 3 strikes = canal removido |
| **Conteúdo reutilizado** (monetização) | canal que só reposta conteúdo alheio sem acrescentar nada | não é aprovado no Programa de Parcerias, ou perde a monetização **do canal inteiro** |

Ter autorização do criador resolve o primeiro, **mas não o segundo**: a política de conteúdo reutilizado
vale mesmo com permissão. Pra passar nos dois, cada corte precisa ter autorização **e** acrescentar algo próprio.

## Regra 1: só usar fontes autorizadas

- Use vídeos de criadores que **liberam cortes publicamente** (muitos streamers têm "programa de clipadores"
  ou dizem na bio/descrição que cortes são permitidos) ou que **autorizaram por escrito**.
- Registre cada fonte e a prova da autorização (print, link, mensagem) em [fontes-de-conteudo.md](fontes-de-conteudo.md).
- **Trailers e vídeos oficiais de publishers** (Rockstar, etc.): use trechos curtos, sempre com comentário
  ou contexto em cima. Repostar o trailer inteiro ou quase inteiro é o caminho mais rápido pra um claim.
- Não use vazamentos (leaks) de material não lançado. Publishers derrubam esse conteúdo com frequência.

## Regra 2: acrescentar valor original em todo corte

O que o CortaGo já acrescenta automaticamente:
- seleção e edição do trecho (o Claude escolhe o momento e o corte respeita início e fim de frase);
- legenda animada palavra por palavra;
- gancho escrito na tela;
- título e descrição próprios;
- música de fundo.

O que fortalece ainda mais (fazer sempre que possível):
- **contexto próprio** no gancho e na descrição (por que esse momento importa);
- **compilações temáticas** (ex.: "5 detalhes do trailer de GTA 6"), em vez de um trecho solto;
- no futuro, **comentário/narração própria**, o sinal mais forte de originalidade.

Evite: o mesmo formato idêntico, em massa, sem variação, com vídeos de uma única fonte. Esse é o padrão
que o YouTube enquadra como "repetitivo / produzido em massa".

## Regra 3: créditos sempre

Todo Short leva na descrição:

```text
Créditos: [nome do canal original] — [link do vídeo original]
```

O CortaGo gera isso automaticamente a partir dos dados do vídeo. Pra arquivos locais, ele escreve
"(arquivo local)": **troque pelo criador real antes de publicar**.

## Regra 4: música só da biblioteca do canal

- Use apenas as faixas de `data/music/`, catalogadas em [musicas.md](musicas.md).
- Fonte aprovada: **Biblioteca de áudio do YouTube**. Os termos foram aceitos em 15/11/2026 ao baixar as faixas.
- Faixa que exige atribuição: criar o `.txt` com o crédito ao lado do arquivo. O CortaGo inclui o crédito
  na descrição sozinho.
- **Nunca** música comercial (Spotify, rádio, trilha de jogo). Mesmo uns segundos geram claim.
- Biblioteca de áudio do YouTube no TikTok/Instagram: a licença é pensada para o YouTube. Antes de postar
  nas outras plataformas, confira os termos da faixa ou use os sons da própria plataforma.

## Se receber um claim ou strike

1. **Claim de Content ID:** veja no Studio → Conteúdo → coluna Restrições. Se a fonte é autorizada, conteste
   anexando a autorização registrada em [fontes-de-conteudo.md](fontes-de-conteudo.md). Se não é, aceite e
   remova a fonte da lista.
2. **Strike de direitos autorais:** não suba nada parecido até resolver. Avalie contranotificação só se a
   autorização for clara. Strikes expiram em 90 dias se você fizer o curso de direitos autorais do YouTube.
3. Registre o ocorrido e o que mudou em [decisoes.md](decisoes.md).
