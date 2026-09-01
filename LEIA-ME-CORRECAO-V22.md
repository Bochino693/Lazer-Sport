# Correção V22 — modais das contas de clientes e envio de ofertas

Pacote cumulativo preparado sobre o commit `bee10e2`. Contém todas as
correções das versões V15 a V21 e pode ser copiado diretamente sobre o
projeto atualizado.

## Aplicar

1. Feche o servidor Django local.
2. Extraia o ZIP.
3. Copie **todo o conteúdo extraído** para a raiz de `Lazer-Sport` e aceite
   substituir os arquivos.
4. Não use `git stash pop`.
5. Com a `.venv` ativa, execute:

```powershell
python manage.py migrate
python manage.py check
git status --short
```

Depois de conferir localmente:

```powershell
git add LEIA-ME-CORRECAO-V22.md core/middleware.py core/templates/gestao/users_adm.html core/views.py sistema_interno
git commit -m "Corrige modais e ofertas das contas de clientes"
git push origin main
```

## Contas de clientes

- Criar e editar continuam na mesma tela.
- Inativar ou reativar agora abre uma confirmação que explica o efeito.
- A inativação bloqueia o login e preserva pedidos, contatos e histórico.
- A ação grava o estado desejado; um clique repetido não reativa por engano
  uma conta que deveria permanecer inativa.
- Excluir exige digitar `EXCLUIR`, e a confirmação também é validada no
  servidor — não depende somente do botão no navegador.
- Contas protegidas (superusuário e a própria conta em uso) continuam sem
  ações destrutivas.

## Cupom, combo e promoção

- A ação de envio abre um modal próprio na linha do cliente.
- O modal recebe as ofertas ativas junto da página e abre sem uma segunda
  busca demorada.
- Seleciona automaticamente o primeiro tipo que possui oferta ativa.
- E-mail e WhatsApp só ficam disponíveis quando a conta tem o contato.
- O envio usa a campanha e o acompanhamento já existentes no painel.
- Cupom exclusivo é vinculado somente à conta escolhida, dentro da mesma
  transação da campanha.
- E-mail entra na fila segura; WhatsApp fica pronto para a confirmação humana
  na tela de acompanhamento.
- Conta inativa não recebe oferta.

## Modais depois de trocar de tela

O controlador saiu do HTML substituído e passou para o bloco de scripts da
tela. Assim ele é executado tanto no carregamento inicial quanto depois da
navegação interna sem recarregar. Ao abrir uma janela, qualquer outra janela
da tela é fechada antes, evitando fundos escuros sem conteúdo ou dois modais
sobrepostos.

## Migração segura para o Render

A conversão das quantidades da O.S. foi separada da alteração de esquema:

- `0038`: normaliza os dados antigos;
- `0039`: confirma a coluna como número inteiro.

Isso evita `pending trigger events` no PostgreSQL. Se a antiga `0038` já foi
aplicada no Render, o Django executará somente a nova `0039`; os dados já
normalizados permanecem iguais.

## Verificação

- `manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: nenhuma migração faltando.
- JavaScript da tela: sintaxe validada.
- 625 testes da suíte completa: aprovados.
