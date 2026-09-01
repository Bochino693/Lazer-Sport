# Correção V18 — um aviso por orçamento

Pacote cumulativo preparado sobre o commit `bee10e2`. Contém as correções
das versões V15, V16 e V17 e pode ser copiado por cima delas.

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
git add LEIA-ME-CORRECAO-V18.md core/middleware.py sistema_interno
git commit -m "Conta notificações por orçamento e não por versão"
git push origin main
```

## Regra corrigida

- O contador usa a negociação original como identidade.
- Thiago com duas versões conta 1.
- Ana com uma versão conta 1.
- Marcelo com três versões conta 1.
- Resultado do exemplo: 3 orçamentos, nunca 6 versões.
- Várias movimentações não lidas no mesmo orçamento continuam explicadas no
  histórico, mas ocupam somente uma unidade no contador.
- O mesmo orçamento vencido, alterado e respondido pode aparecer com seus
  motivos separados na central, mas continua contando apenas uma vez no sino
  e no menu Orçamentos.
- A atualização entre usuários continua em tempo real e a marcação de leitura
  continua sendo feita pelo último evento efetivamente recebido pela tela.

## Verificação

- `manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: nenhuma migração faltando.
- Casos automatizados cobrem cadeias com 2, 1 e 3 versões e a sobreposição de
  vários motivos no mesmo orçamento.
- As migrações `0037` e `0038` continuam presentes porque o pacote é
  cumulativo; se já foram aplicadas, não serão repetidas.
