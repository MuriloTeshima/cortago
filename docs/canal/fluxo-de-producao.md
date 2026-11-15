# Fluxo de produção

Do vídeo de origem ao Short publicado.

```text
1. Escolher fonte → 2. Gerar cortes → 3. Revisar → 4. Publicar → 5. Registrar
```

## 1. Escolher a fonte

- O vídeo é de uma fonte **autorizada** em [fontes-de-conteudo.md](fontes-de-conteudo.md)?
  Se não, peça autorização antes (modelo no mesmo arquivo) ou escolha outro vídeo.
- Prefira vídeos com fala clara: o CortaGo escolhe os cortes pela transcrição.

## 2. Gerar os cortes

```bash
uv run cortago serve        # abre http://127.0.0.1:8000
```

- Cole a URL e escolha a quantidade de cortes (5 é um bom padrão).
- **Layout:** `blur` (vídeo inteiro com fundo desfocado) para gameplay e trailers, porque preserva HUD e mapa;
  `crop` para câmera de rosto / pessoa falando.
- **Música de fundo:** deixe marcada, a não ser que o vídeo já tenha trilha.

## 3. Revisar cada corte (checklist)

- [ ] O corte faz sentido sozinho, sem precisar do resto do vídeo?
- [ ] Os 2 primeiros segundos prendem? Se não, ajuste o **início** ou o **gancho**.
- [ ] Termina numa frase completa?
- [ ] Legenda sem erro grosseiro nos nomes (personagens, jogos)?
- [ ] Título verdadeiro e específico?
- [ ] Música combina com o clima e não atrapalha a fala? Se estiver alta, use **−** ao lado da faixa;
      se não combinar, troque na edição.
- [ ] **Créditos corretos** no texto (em arquivo local, trocar "(arquivo local)" pelo criador real)
- [ ] Nada de leak, conteúdo +18 explícito ou ofensivo

Aprovado → **Aprovar**. Ruim → **Descartar** (melhor descartar do que publicar um corte fraco).

## 4. Publicar

Enquanto o envio automático não existe:

1. **Baixar** o vídeo no card do corte.
2. **Copiar texto** (título, descrição, créditos e hashtags prontos).
3. YouTube Studio → Criar → Enviar vídeos. Colar título e descrição, conferir categoria Jogos e
   "não é conteúdo para crianças" (já vêm dos padrões de envio, ver [criacao-do-canal.md](criacao-do-canal.md)).
4. Publicar ou agendar.
5. Repostar no TikTok e no Instagram (ver a nota sobre músicas em [politicas-e-direitos.md](politicas-e-direitos.md#regra-4-música-só-da-biblioteca-do-canal)).

## 5. Registrar

- Novas fontes autorizadas → [fontes-de-conteudo.md](fontes-de-conteudo.md)
- Aprendizados (o que funcionou ou não) → [decisoes.md](decisoes.md)
- Problemas ou ideias de melhoria na ferramenta → issue no GitHub do repositório
