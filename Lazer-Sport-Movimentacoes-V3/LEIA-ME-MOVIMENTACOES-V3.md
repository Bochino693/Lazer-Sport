# Movimentações V3 — cliente, busca e exclusão segura

Pacote cumulativo para aplicar sobre o commit `d1a9df3`.

## Resultado

- Cliente aparece somente quando o tipo é **Saída**.
- Saída não é registrada sem cliente.
- Busca de clientes igual à do orçamento, sem carregar a carteira inteira.
- A pesquisa aceita nome, contato e dados indexados pelo cadastro central.
- “Cadastrar cliente” abre no próprio movimento, salva a ficha e já seleciona.
- Cadastro contém tipo, contato, documento, buffet e endereço com consulta de CEP.
- Modal de movimentação reorganizado para computador e tablet, com rolagem interna.
- Entrada soma; saída subtrai; ajuste define a contagem real.
- Somente superusuário pode excluir movimentações.
- Exclusão aparece apenas no movimento mais recente de cada item e restaura o saldo anterior.

## Aplicar

Extraia o ZIP na raiz do projeto e aceite substituir os arquivos. Em seguida:

```powershell
python manage.py migrate
python manage.py check
git add sistema_interno
git commit -m "Melhora movimentacoes e associacao de clientes"
git push origin main
```

A migração `0053_movimento_estoque_cliente.py` já deve estar no projeto, pois
foi incluída no pacote anterior e no commit `d1a9df3`.

## Teste rápido

1. Abra um material e clique em movimentar.
2. Em Entrada, o cliente não aparece.
3. Escolha Saída: a busca de cliente deve aparecer.
4. Pesquise Marcos ou use Cadastrar cliente.
5. Com saldo 10, registre saída 3; o saldo deve ficar 7.
6. No Histórico, o superusuário verá a lixeira apenas no último movimento do item.
