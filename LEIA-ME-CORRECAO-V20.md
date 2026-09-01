# Correção V20 — valor dos itens da O.S.

Pacote cumulativo preparado sobre o commit `bee10e2`. Contém todas as
correções das versões V15 a V19 e pode ser copiado diretamente sobre o
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
git add LEIA-ME-CORRECAO-V20.md core/middleware.py sistema_interno
git commit -m "Corrige valor dos itens da ordem de serviço"
git push origin main
```

## Valor unitário da O.S.

- Uma linha nova abre com o campo realmente vazio.
- `0,00` é somente o placeholder e não participa da digitação.
- Digitar `400` representa R$ 400,00; ao sair do campo, aparece `400,00`.
- Também é possível escrever centavos, por exemplo `400,50`.
- Preços de itens existentes e valores vindos do catálogo continuam sendo
  carregados e formatados como valores completos.
- O subtotal é recalculado durante a digitação com o valor real informado.

## Correções cumulativas mantidas

- Menu do tablet fecha antes e depois da troca de tela.
- Gravações de O.S. e orçamento evitam consultas e recargas redundantes.
- O.S. usa quantidade inteira e campos adequados ao tipo da linha.
- WhatsApp não cria página `about:blank` e reutiliza uma única aba Web.
- Notificações de orçamento contam propostas distintas, não suas versões.
- Resiliência de rede, modais, impressão, etiquetas e versões permanece
  incluída conforme as correções anteriores.

## Verificação

- `manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: nenhuma migração faltando.
- Máscara validada para campo vazio, `4`, `40`, `400`, `400,50` e valor
  colado no formato `R$ 1.234,56`.
- JavaScript do painel passou na verificação de sintaxe.
- As migrações `0037` e `0038` continuam presentes porque o pacote é
  cumulativo; se já foram aplicadas, não serão repetidas.
