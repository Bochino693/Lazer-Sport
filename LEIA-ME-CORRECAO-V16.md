# Correção V16 — WhatsApp, campos da O.S. e recuperação de conexão

Pacote cumulativo preparado sobre o commit `bee10e2`. Se a V15 já foi
aplicada, esta V16 pode ser copiada por cima. Se ainda não foi, a V16 também
contém as correções da V15.

## Aplicar

1. Feche o servidor Django.
2. Extraia o ZIP.
3. Copie **todo o conteúdo extraído** para a raiz de `Lazer-Sport` e aceite
   substituir os arquivos.
4. Não use `git stash pop`: o stash existente é do pacote antigo.
5. Com a `.venv` ativa, execute:

```powershell
python manage.py migrate
python manage.py check
python manage.py test sistema_interno.tests_resiliencia sistema_interno.tests_espera sistema_interno.tests_orcamento sistema_interno.tests_os_versoes sistema_interno.tests_os_etapas sistema_interno.tests_orcamento_os_separados --settings=lazer.settings_test
git status --short
```

Depois de conferir localmente:

```powershell
git add LEIA-ME-CORRECAO-V16.md core/middleware.py sistema_interno
git commit -m "Corrige WhatsApp, campos da OS e recuperação de conexão"
git push origin main
```

## Correções desta versão

- “Copiar mensagem e ir ao WhatsApp” nunca abre uma URL vazia. O sistema
  foca uma aba válida ou abre uma URL real do WhatsApp Web no próprio clique.
- No PC, “Abrir WhatsApp” usa uma única aba nomeada do WhatsApp Web, sem
  sondagem silenciosa do aplicativo nativo.
- Quantidade de item da O.S. é inteiro positivo na interface, validação e
  banco. A migração converte os valores antigos antes de alterar a coluna.
- `1,5` é recusado com uma mensagem clara; não vira `1`, `15` ou outro valor.
- O tipo da linha muda a grade: peça/material tem catálogo e descrição;
  serviço, deslocamento e outro mostram somente Tipo, Quantidade, Valor e
  Subtotal. Cada campo possui seu próprio rótulo.
- Uma linha simples não consegue guardar escondido o vínculo de uma peça.
- Na lista de O.S., o selo de situação ficou centralizado e perdeu a segunda
  caixa verde desalinhada. A identificação da O.S. não quebra em três linhas.
- Quedas de conexão PostgreSQL no painel fecham a conexão inutilizável e
  devolvem a tela recuperável, sem transformar o problema em uma página 502.
- GETs transitórios continuam sendo repetidos com segurança; POSTs nunca são
  repetidos automaticamente, evitando pagamento, exclusão ou versão duplicada.

## Verificação

- `manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: nenhuma migração faltando.
- 169 testes relevantes aprovados (151 do fluxo principal + 18 de utilitários).
- Python, JavaScript e CSS passaram nas verificações de sintaxe/estrutura.

Observação: nenhum software consegue impedir uma indisponibilidade física do
Render ou da internet. Esta correção garante que as falhas transitórias
alcançadas pelo aplicativo sejam tratadas sem apagar a tela boa e sem repetir
gravações perigosas.
