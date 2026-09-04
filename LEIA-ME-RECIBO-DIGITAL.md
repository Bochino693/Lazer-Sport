# Recibo digital do orçamento pago

Antes, o dinheiro que entrava virava um campo (`valor_pago`) e um selo
"Pago" na lista. Bastava para a empresa e não bastava para o cliente:
quem paga uma festa de R$ 23.980,00 pede o comprovante com CNPJ, número,
data e o valor por extenso — e buffet, condomínio e prefeitura precisam
anexar esse papel à prestação de contas. O que existia era alguém da
equipe escrevendo um recibo à mão num modelo de Word.

Agora o orçamento com valor recebido tem, no menu **Ações**, a opção
**Gerar recibo**.

## Aplicar

Com a `.venv` ativa, na raiz do projeto:

```powershell
python manage.py migrate
python manage.py check
```

A migração `sistema_interno/0053_recibo_de_pagamento` só cria a tabela
nova; nenhum dado existente é tocado.

## Como funciona na tela

1. Na lista de **Orçamentos**, a proposta aprovada com pagamento
   registrado ganha **Gerar recibo** no menu de ações.
2. A janela mostra o total da proposta, quanto já entrou e **quanto
   falta emitir recibo**. Não há campo de valor: o recibo sai do
   pagamento registrado, e nunca de um número digitado — recibo e
   planilha divergindo é um papel que deixa de valer.
3. Emitido, o link fica ali para copiar e mandar ao cliente, que abre
   uma página da Lazer & Sport com o comprovante e pode salvar em PDF ou
   imprimir (uma folha A4).
4. O número do último recibo passa a aparecer na coluna **Pagamento** da
   lista — é a resposta rápida para "esse já tem recibo?".

**Quem emite:** Financeiro ou Gestão, a mesma permissão de registrar
pagamento — quem declara que o dinheiro entrou responde pelo documento
que afirma isso. O comercial vê e compartilha o recibo já emitido.

## Pagamento em parcelas

Cada recibo cobre **o que entrou desde o recibo anterior**. Um sinal de
R$ 5.000,00 gera o 1º recibo por R$ 5.000,00, marcado como *recebimento
parcial* e com o saldo em aberto no documento; quitado o restante, o 2º
recibo sai pela diferença e traz *quitação total*. Somando os recibos de
uma proposta dá exatamente a venda — e não o dobro dela, que é o que
aconteceria se cada papel repetisse o acumulado.

Apertar o botão duas vezes não gera dois números para o mesmo dinheiro:
sem valor novo registrado, a janela avisa que já está tudo documentado.

## O que faz este papel valer

- **Valor por extenso**, como todo recibo escreve: é o que impede um
  "1.500,00" de virar "11.500,00" com uma canetada depois de impresso.
- **Documento imutável**: os valores ficam gravados no recibo, e não
  lidos do orçamento na hora de desenhar a página. Corrigir o orçamento
  amanhã não muda o papel que o cliente já guardou.
- **Código de verificação e impressão digital (SHA-256)** no rodapé. Se
  a linha for alterada por fora, a própria página avisa que o documento
  não confere com o registro original, em vez de exibir um comprovante
  adulterado com cara de bom.
- **Link próprio**, separado do link da proposta: quem paga nem sempre é
  quem negociou, e o comprovante circula sem levar junto o preço
  unitário de cada item e a margem da negociação.

## Arquivos

| Onde | O quê |
|---|---|
| `sistema_interno/recibos.py` | quando emitir, por quanto e como conferir |
| `sistema_interno/models.py` | `ReciboOrcamento` (imutável) e `Orcamento.pode_emitir_recibo` |
| `core/views_recibo.py`, `core/templates/recibo_pagamento.html` | a página que o cliente abre |
| `core/formatos.py` | `por_extenso` — o valor escrito |
| `sistema_interno/views_gestao.py` | a ação `recibo` do painel |

## Verificação

- `manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: nada pendente além do que já
  existia antes desta mudança.
- `sistema_interno/tests_recibo.py`: 19 testes novos (emissão, parcelas,
  duplicidade, imutabilidade, permissão, página pública).
- `core/tests_formatos.py`: o valor por extenso, incluindo "mil" sem o
  "um" e "dois milhões **de** reais".
- Suíte completa: aprovada.
