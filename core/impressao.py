"""Quanto conteúdo cabe numa folha A4 — e quão apertado ele precisa sair.

O PROBLEMA QUE ISTO RESOLVE.

O orçamento e a Ordem de Serviço precisam sair em uma folha só. O jeito
antigo de garantir isso era encolher tudo até caber a maior proposta
imaginável: corpo de 8px, rótulos de 5,2pt, recuos de 1,2mm. Funcionava,
e o preço era que TODA proposta pagava pelo tamanho da maior -- o cliente
recebia uma A4 com o documento espremido no terço de cima e quase metade
da folha em branco.

Tamanho fixo não resolve isto porque o problema não é fixo: uma proposta
de dois itens e uma de vinte não cabem no mesmo corpo de letra. A saída é
o documento saber quanto conteúdo carrega e escolher a densidade -- solto
quando é curto, apertado quando é longo.

POR QUE A CONTA É FEITA AQUI, E NÃO NO CSS.

Dá para contar linhas em CSS com `:has()` e `:nth-of-type()`. Mas
`:nth-of-type` conta por TIPO de elemento, não por classe: no orçamento,
as linhas de item são `div` no meio de outros `div` (o título do bloco, o
cabeçalho da tabela), e "o nono div" não é "o nono item". A regra
passaria a depender de quantas `div` existem antes da lista -- quer
dizer, quebraria silenciosamente na próxima vez que alguém acrescentasse
um aviso no topo do bloco.

E o CSS não sabe contar o que não é linha. Uma O.S. de quatro itens com
um diagnóstico de dez linhas, seis fotos e o quadro do Pix ocupa mais
folha do que uma de doze itens secos. Contar só `<tr>` acertaria a
primeira e erraria a segunda.

Aqui a conta é do documento inteiro, e tem teste.
"""

import math

#: Quantos caracteres cabem numa linha impressa, na largura de um campo
#: de texto do documento. Medido no layout, não chutado: os campos ficam
#: dois por linha numa folha de 192mm.
CARACTERES_POR_LINHA = 95

#: Quantas linhas o quadro de pagamento (QR do Pix, código copia-e-cola e
#: os dois cartões de banco) come da folha quando aparece.
LINHAS_DO_PAGAMENTO = 7

#: Quantas fotos cabem numa faixa da galeria.
FOTOS_POR_FAIXA = 6

#: Os degraus. Saíram de medir os documentos renderizados contra a altura
#: útil da A4 (277mm): até 10 linhas o documento sobra folha e estica
#: para preencher; até 18 ele chega perto da borda; acima disso só cabe
#: no tamanho mínimo -- e há documentos que honestamente não cabem, e
#: nesse caso viram duas páginas em vez de um papel ilegível.
SOLTO_ATE = 10
DENSO_ATE = 18


def linhas_de_texto(*textos):
    """Quantas linhas impressas estes textos livres ocupam."""
    return sum(
        math.ceil(len(t.strip()) / CARACTERES_POR_LINHA)
        for t in textos
        if t and t.strip()
    )


def peso_do_documento(itens=0, textos=(), fotos=0, com_pagamento=False):
    """O tamanho do documento em linhas impressas equivalentes.

    Cada item é uma linha. Cada campo de texto livre vale as linhas que
    de fato ocupa. Fotos e o quadro de pagamento entram pelo espaço que
    tomam, porque para a folha tanto faz se o que a encheu foi tabela ou
    imagem.
    """
    peso = max(int(itens or 0), 0)
    peso += linhas_de_texto(*textos)
    peso += math.ceil(max(int(fotos or 0), 0) / FOTOS_POR_FAIXA) * 2
    if com_pagamento:
        peso += LINHAS_DO_PAGAMENTO
    return peso


def densidade(peso):
    """Qual das três densidades este documento pede.

    Devolve o nome que vira classe no `<body>` -- é o CSS de impressão
    que sabe o que cada uma significa. Aqui mora só a regra de QUANDO,
    que é a parte que muda quando o layout muda e a parte que precisa ser
    conferida.
    """
    peso = max(int(peso or 0), 0)
    if peso <= SOLTO_ATE:
        return "folha-solta"
    if peso <= DENSO_ATE:
        return "folha-densa"
    return "folha-apertada"
