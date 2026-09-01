# Correção V21 — contador real de orçamentos pendentes

Pacote cumulativo preparado sobre o commit `bee10e2`. Contém todas as
correções das versões V15 a V20 e pode ser copiado diretamente sobre o
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
git add LEIA-ME-CORRECAO-V21.md core/middleware.py sistema_interno
git commit -m "Corrige contador de orçamentos pendentes"
git push origin main
```

## Número ao lado de Orçamentos

O contador agora representa a fila comercial ainda não finalizada:

- Rascunho: conta.
- Aguardando resposta: conta, mesmo sem validade ou com validade distante.
- Em negociação: conta.
- Aprovado, recusado ou expirado: não conta.
- Versão substituída: não conta.
- Uma proposta com v1, v2 ou v3 ocupa somente uma unidade; apenas a versão
  atual entra na fila.

Os avisos de vencimento, proximidade da validade e movimentação de outro
usuário continuam separados na central. Eles não alteram nem duplicam o
número da fila comercial.

Na relação informada durante a correção, os IDs 17, 16, 15v2, 14v2, 11 e 9
estão em aberto; portanto o número esperado é 6, e não 2.

## Atualização dinâmica

- Uma gravação feita pelo próprio usuário invalida imediatamente seu contador.
- Alterações feitas por outro usuário são detectadas pelo pulso da central de
  avisos e atualizam a bolinha sem recarregar a página.
- O toque de notificação continua reservado para movimentações novas; a fila
  em aberto permanece visível enquanto houver trabalho pendente.

## Verificação

- `manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: nenhuma migração faltando.
- Testes cobrem os estados abertos, estados finalizados e cadeias com versões.
- As migrações `0037` e `0038` continuam presentes porque o pacote é
  cumulativo; se já foram aplicadas, não serão repetidas.
