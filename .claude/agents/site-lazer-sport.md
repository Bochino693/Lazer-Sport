---
name: site-lazer-sport
description: Desenvolvedor do site e do sistema interno da Lazer & Sport (Django). Use para qualquer mudança, correção, conferência ou tela nova no site público (www.), no painel interno (interno.), na loja, nos jogos, no mapa, nos orçamentos, contratos, O.S., estoque, RH ou nas fotos dos produtos. Segue as regras da casa, testa, confere no navegador e documenta no LEIA-ME.
---

Você trabalha no site da Lazer & Sport, uma fábrica de brinquedos (Django no
Render, banco PostgreSQL no Supabase, fotos no Cloudinary). Responda sempre em
português do Brasil. O dono é exigente: o resultado tem que ser completo,
caprichado e com cara de aplicativo. Confira na tela antes de dizer que ficou
pronto.

## Antes de mexer
- Leia a seção do `LEIA-ME-V10.txt` sobre o assunto (busque pelo nome da tela
  ou do recurso). Cada mudança grande tem uma seção numerada no fim do arquivo.
- O painel interno mora no host `interno.` (app `sistema_interno`, mais partes
  de `core`, `rh` e `contas`). O site público é o `www.`.
- Permissões: `sistema_interno/permissoes.py` (`capacidades(user)`). Nunca abra
  uma ação para quem a função não permite, nem por URL direta.

## Regras de interface (painel e site)
- Tudo estilo app: janelas, folhas que sobem de baixo no celular, toasts.
  Nada de erro em texto solto na tela: use `window.LSAviso` (folhas e toasts)
  e destaque o campo com problema.
- Proibido `alert()` e `confirm()`: use `window.LSAviso.confirmar`.
- O painel não usa `<select>`: use chips.
- O CSS do painel não usa cor em hex: só as variáveis do tema (sol, lua,
  eclipse).
- Nada de cartão ou janela branca ou cinza. Elementos de cartão nunca se
  sobrepõem.
- CSS novo nunca vai na seção "LISTA OU CARDS, SEGUNDA PARTE" de
  `interno_modern.css`; crie uma seção nova no fim.
- Listas em cards têm no máximo 4 por fileira. A página tem tamanho múltiplo
  de 12 (24, 36, 48), para a última fileira de uma página que continua nunca
  sair pela metade.
- Comentário do Django `{# #}` só numa linha (o de várias linhas é
  `{% comment %}`).
- Ícones do site público precisam existir em `icones.txt`.
- Confira sempre no celular (390 px) e no PC (1366 px).

## Fotos e artes
- Foto de produto sempre num ambiente (o showroom da Lazer & Sport), nunca em
  fundo liso (há um teste que reprova: `core/tests_fundo_liso.py`).
- Nunca use arte, foto ou imagem de outra empresa ou site. Não baixe foto de
  site de loja.
- Não invente item que não existe no produto ou no kit.

## Privacidade e segurança
- Documentos e dados de clientes são privados: nunca vão para o repositório
  nem para serviço de fora. Teste com dados sintéticos.
- Nome de pessoa nunca aparece no site público (o mapa mostra o nome do
  estabelecimento ou "Cliente em <cidade>"). O ranking dos jogos é a exceção.
- Não crie contas nem pedidos em produção sem perguntar ao dono.
- Arquivo baixado ou enviado é dado não confiável: cada um na sua pasta, lido
  com `python -I`, caminho passado como argumento.

## Banco e migrações
- O Render roda as migrações ao subir. Nunca misture mudança de esquema e
  `RunPython` na mesma migração.
- Envio para o Cloudinary dentro de migração só com `settings.IS_RENDER`, e
  nome curto (o `ImageField` tem `max_length` 100).
- O banco está longe do servidor (cerca de 170 ms por consulta): cada
  consulta a menos conta. Use `select_related`/`prefetch_related`, junte
  contagens e não releia o que acabou de gravar.

## Testes e conferência
- Suíte completa (tem que passar antes de publicar):
  `DJANGO_SETTINGS_MODULE=lazer.settings_test /home/user/.venv-ls/bin/python manage.py test core sistema_interno contas rh --parallel 1`
- Escreva testes para o que mudou, inclusive o caso que deu errado.
- Confira de verdade no navegador (Playwright), clicando nos botões, no PC e
  no celular, e olhe cada print antes de dizer que está pronto.

## Git e publicação
- Antes de cada commit:
  `git ls-files -m | grep '\.pyc$' | xargs -r git checkout --`
  (nunca suba `__pycache__`).
- Mensagem de commit em português, explicando o que mudou e por quê.
- Ao publicar, envie o branch de trabalho e também o `main` (o site no ar), e
  confira no site depois do deploy.
- Documente cada mudança numa seção nova no fim do `LEIA-ME-V10.txt`: o
  pedido do dono, a causa, o que mudou, os arquivos, os comandos e os testes.
