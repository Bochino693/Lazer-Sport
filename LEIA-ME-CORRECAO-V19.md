# Correção V19 — menu do tablet e gravação rápida

Pacote cumulativo preparado sobre o commit `bee10e2`. Contém todas as
correções das versões V15 a V18 e pode ser copiado por cima delas.

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
git add LEIA-ME-CORRECAO-V19.md core/middleware.py sistema_interno
git commit -m "Acelera gravações e fecha menu do tablet"
git push origin main
```

## Menu do tablet

- Fecha no próprio toque do destino, antes de iniciar a requisição.
- Fecha novamente depois de montar a nova tela.
- Remove a gaveta, o fundo escuro e também o modo de trilho expandido usado
  entre 761 e 1100 px.
- O estado expandido continua podendo ser lembrado no PC, mas não reaparece
  cobrindo uma tela nova no tablet.

## Gravação mais rápida

- Um GET recente da navegação ou da central de avisos passa a comprovar que
  Django e banco já estão acordados. O POST não espera outro `/pronto/`
  redundante.
- Itens de orçamento são resolvidos em lote: no máximo uma consulta por
  catálogo, independentemente de haver uma ou vinte linhas.
- Peças da O.S. são resolvidas em uma consulta para a lista inteira.
- Os itens recém-gravados são reaproveitados para calcular o total da resposta,
  sem uma leitura adicional do banco.
- Orçamento novo cria os dois blocos de revisão em uma única operação.
- Depois da confirmação do POST, o modal fecha e somente o conteúdo da tela é
  atualizado; menu, fontes e scripts globais não são recarregados.
- POST continua sendo enviado uma única vez. Nenhuma otimização repete
  pagamento, exclusão ou criação em caso de rede lenta.

## Verificação

- `manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: nenhuma migração faltando.
- Teste de desempenho compara gravação com 1 e 20 itens e impede a volta de
  consultas por linha.
- JavaScript da navegação, painel e menu passou na verificação de sintaxe.
- As migrações `0037` e `0038` continuam presentes porque o pacote é
  cumulativo; se já foram aplicadas, não serão repetidas.
