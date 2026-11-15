# Criação do canal: checklist

Siga em ordem. Marque `[x]` conforme for fazendo.

## 1. Conta

- [ ] Decidir: usar a conta Google atual ou criar uma **conta Google só para o canal**.
  Uma conta separada é mais segura e permite passar o canal para uma conta de marca ou para outra pessoa
  no futuro sem misturar com seu e-mail pessoal.
- [ ] Ativar **verificação em duas etapas** na conta. Canal sem 2FA é alvo comum de roubo.
- [ ] Guardar os códigos de recuperação num lugar seguro (gerenciador de senhas), **fora deste repositório**.

## 2. Criar o canal

- [ ] youtube.com → foto do perfil → **Criar um canal**
- [ ] Nome: `Game Cuts`
- [ ] @: `GameCutsBR` (se não estiver mais livre, use `GameCutsOficial` e atualize [identidade.md](identidade.md))
- [ ] Foto do canal: `CorteGamer/profileImg.png`
- [ ] Banner: `CorteGamer/banner_2560x1440.png` (já no formato do YouTube; ver
  [identidade.md](identidade.md#arquivos-das-artes-cortegamer))
- [ ] Descrição do canal ([identidade.md](identidade.md#descrição-do-canal-youtube))
- [ ] E-mail de contato comercial (Personalização → Informações básicas)

## 3. Verificar o canal

- [ ] studio.youtube.com → Configurações → Canal → **Qualificação de recursos** → verificar por telefone.
  Isso libera os recursos intermediários (vídeos com mais de 15 min, miniaturas personalizadas, lives).
  Os avançados vêm depois, com histórico do canal ou verificação de identidade.

## 4. Configurações do YouTube Studio

**Configurações → Canal → Informações básicas**
- [ ] País: Brasil
- [ ] Palavras-chave: as de [identidade.md](identidade.md#palavras-chave-do-canal)

**Configurações → Canal → Configurações avançadas**
- [ ] Público: **"Não, configurar este canal como não destinado a crianças"**. Conteúdo marcado como infantil
  perde comentários e boa parte da monetização. O conteúdo de GTA tem classificação adulta, então não é para crianças mesmo.

**Configurações → Padrões de envio** (vale para todo vídeo novo)
- [ ] Categoria: **Jogos**
- [ ] Idioma do vídeo e do título: **Português (Brasil)**
- [ ] Licença: Licença padrão do YouTube
- [ ] Descrição padrão:

  ```text
  [descrição do corte]

  Créditos: [canal original] — [link do vídeo original]

  #shorts #games
  ```

  O CortaGo já gera esse texto pronto para cada corte (botão "Copiar texto").

- [ ] Comentários: permitir, retendo os potencialmente inadequados para revisão

**Configurações → Comunidade**
- [ ] Palavras bloqueadas: spam comum ("ganhe dinheiro", links de golpe)

## 5. Outras plataformas (mesmo dia)

- [ ] TikTok: conta **@GameCutsBR**, mesma foto e bio curta
- [ ] Instagram: conta **@GameCutsBR** (conta profissional/criador para ver as estatísticas)
- [ ] Atualizar os links no YouTube (Personalização → Informações básicas → Links)

## 6. Integração com o CortaGo (quando for publicar direto pela ferramenta)

- [ ] Criar um projeto no Google Cloud e ativar a **YouTube Data API v3**
- [ ] Criar credenciais OAuth (tipo "App para computador")
- [ ] Guardar as credenciais em `.env` / arquivo ignorado pelo git, **nunca neste repositório**
- [ ] Cota padrão: cerca de 6 envios por dia. Pedir aumento se precisar

Esta etapa ainda depende da funcionalidade de upload no CortaGo, que ainda não foi construída.

## 7. Antes do primeiro Short

- [ ] Ler [politicas-e-direitos.md](politicas-e-direitos.md)
- [ ] Ter pelo menos 1 fonte autorizada em [fontes-de-conteudo.md](fontes-de-conteudo.md) ou um plano de comentário próprio
- [ ] Deixar 5–10 cortes prontos antes de lançar, pra manter a frequência na primeira semana
