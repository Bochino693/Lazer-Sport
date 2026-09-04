# Vendas: do pagamento ao comprovante assinado

## O problema que isto resolve

A empresa recebe por três caminhos — a proposta comercial (orçamento), a
ordem de serviço e o pedido da loja online — e cada um guardava o seu
dinheiro do seu jeito:

- **A tela financeira somava só a loja.** Uma proposta de R$ 20.000 paga
  no balcão não existia no gráfico. O "ticket médio da fábrica" era o
  ticket médio de quem compra peça pelo site.
- **`valor_pago` é um acumulado.** Ele responde "quanto falta" e esquece
  *quando* cada pedaço entrou. Entrada em janeiro e o resto em abril
  apareciam como um valor só, na data da última mexida no documento.
- **O cliente que pagava não recebia nada.** Nem comprovante do que
  pagou, nem documento assinado dizendo o que foi vendido.

## A unidade: a venda

Uma **venda** (`sistema_interno.Venda`) é **uma parcela recebida**: valor,
data, origem e de qual documento veio. É o que permite somar receita por
mês sem contar ninguém duas vezes e sem inventar data.

Ela **nasce sozinha**: quem cria é o próprio `registrar_pagamento` do
orçamento ou da O.S. Registrar pagamento e registrar venda são o mesmo
ato — separá-los em dois cliques garantiria que um dia só o primeiro
aconteceria.

A parcela é a **diferença** entre o que o documento passou a ter e o que
já estava registrado. Quitar uma proposta de R$ 1.000 depois de uma
entrada de R$ 300 registra R$ 700, não R$ 1.000 de novo.

Correção para menos (estorno, digitação errada) **não** vira venda
negativa: é uma correção do documento, e quem conta a receita é a soma
das parcelas que existiram.

O pedido da loja continua no `core.Venda` de sempre e é **lido** de lá —
não foi migrado, para não mexer no checkout.

## O comprovante

Com dinheiro registrado, a lista de orçamentos mostra **Gerar documento**
(função Financeiro ou Gestão). Um clique:

1. pega a venda daquele recebimento;
2. marca o comprovante como emitido;
3. devolve o **link público** e o link da **prévia interna** (para
   conferir e imprimir).

O cliente abre `/venda/<token>/`, confere o que comprou, quanto pagou e
quanto falta, e **assina eletronicamente**: nome, CPF/CNPJ válido e
consentimento. A partir daí o mesmo link vira recibo, com código de
verificação, e a equipe é avisada.

O que sustenta a assinatura sem senha é o mesmo da proposta:

- token com ~190 bits de aleatoriedade — não se chega ao comprovante de
  um cliente adivinhando o de outro;
- assina-se **uma vez**;
- o conteúdo assinado é congelado num hash (`AceiteVenda.venda_hash`): se
  o documento mudar depois, a conferência acusa;
- IP e navegador viram HMAC, nunca texto — mesma regra do
  `AceiteOrcamento`;
- o documento informado é guardado só em dígitos e aparece mascarado.

Comprovante **sem valor recebido não existe**: seria um papel afirmando o
que não aconteceu.

## A tela de Vendas

`/vendas/inner/` mostra as três origens juntas:

- **Recebido no período**, quantidade de vendas e ticket médio;
- **Ainda a receber**, separado de propósito — saldo a receber é
  promessa, e misturar promessa com caixa é como uma empresa descobre
  tarde que faturou no papel e não no banco;
- **Comprovantes assinados** e quantos aguardam assinatura;
- **Sem documento**: recebimentos que ainda não viraram comprovante. É a
  fila de trabalho, e é o que a bolinha do menu passou a contar;
- **gráfico mensal empilhado** por origem, desenhado no servidor em CSS —
  a tela abre pronta, sem biblioteca e sem segunda requisição;
- a lista das últimas vendas, com o estado do comprovante e o atalho para
  o documento.

O **Financeiro** (`/financeiro/`) passou a usar a mesma fonte: a receita
mensal e o ticket médio somam orçamentos, ordens de serviço e loja.

## Histórico

A migração `0054_vendas_do_historico` cria a venda inicial de cada
proposta e cada O.S. que já tinham valor recebido — sem ela, a tela
nasceria vazia e o financeiro contaria como se a empresa tivesse começado
hoje. A data é a melhor que existe (`pago_em`, senão a última
atualização): um pagamento parcial antigo não carimba `pago_em`, então aí
ela é aproximada, o que põe o valor no mês certo ou vizinho em vez de
empilhar o histórico inteiro no dia da migração.

## Onde mexer

| Assunto | Arquivo |
|---|---|
| Regra da parcela, estatística, fila | `sistema_interno/vendas.py` |
| Modelos `Venda` e `AceiteVenda` | `sistema_interno/models.py` |
| Assinatura (hash, HMAC, canônico) | `sistema_interno/assinaturas.py` |
| Ação do painel | `OrcamentosInnerView.acao_documento_venda` |
| Página do cliente | `core/views_venda.py`, `core/templates/venda_publica.html` |
| Prévia interna | `VendaPreviaInnerView` |
| Tela de Vendas | `sistema_interno/views.py` (`VendasView`), `templates/vendas_inner.html` |
| Testes | `sistema_interno/tests_vendas.py` |
