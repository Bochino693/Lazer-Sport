# Correção V15 — notificações, orçamentos e itens da O.S.

Este pacote foi preparado sobre o commit `bee10e2`, exatamente o commit que
já está na sua pasta local. Ele contém somente os arquivos que precisam ser
substituídos ou adicionados.

## Como aplicar

1. Feche o servidor Django.
2. Extraia o ZIP.
3. Abra a pasta extraída e copie **todo o conteúdo dela** para a raiz de
   `Lazer-Sport`, aceitando substituir os arquivos existentes.
4. Não execute `git stash pop`: o `stash@{0}` é o backup antigo da V14.
5. Com a sua `.venv` ativa, execute:

```powershell
python manage.py migrate
python manage.py check
python manage.py test sistema_interno.tests_avisos sistema_interno.tests_orcamento sistema_interno.tests_os_versoes --settings=lazer.settings_test
git status --short
```

Depois de conferir a tela:

```powershell
git add LEIA-ME-CORRECAO-V15.md sistema_interno
git commit -m "Corrige notificações, orçamento e itens da OS"
git push origin main
```

## O que foi corrigido

- O número do sino agora soma ocorrências, não apenas categorias de aviso.
- Alterações de orçamento feitas por outro usuário chegam ao painel aberto em
  até 12 segundos, sem recarregar a página.
- A notificação toca três notas curtas e agradáveis após a primeira interação
  do usuário com a página, respeitando a regra de áudio do navegador.
- Abrir o sino marca somente as atividades que já apareceram; uma novidade que
  chegue durante o clique não é perdida.
- A tabela de orçamentos no PC foi reduzida de dez para oito colunas úteis:
  itens e total foram agrupados, assim como situação e validade.
- Data de validade e avaliações Comercial/Financeiro não ficam mais quebradas
  em várias linhas estreitas.
- Na O.S., peça/material mantém catálogo e descrição. Serviço, deslocamento e
  outros escondem esses dois campos exclusivos e deixam quantidade, valor e
  subtotal alinhados com os cabeçalhos.
- A nova tabela de atividades possui proteção durante a implantação: antes do
  `migrate`, uma falha nela não derruba o painel com erro 502.

## Verificação feita antes do pacote

- `python manage.py check`: sem problemas.
- `python manage.py makemigrations --check --dry-run`: nenhuma alteração
  pendente.
- 134 testes de avisos, orçamentos e ordens de serviço: todos aprovados.
- Python, JavaScript e CSS verificados sem erro de sintaxe/estrutura.
