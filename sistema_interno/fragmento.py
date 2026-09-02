"""Responder só o pedaço que muda quando o filtro muda.

O QUE ESTAVA ACONTECENDO

Clicar em "Aguardando peça" na tela de Ordens de Serviço baixava 380 KB.
Clicar de volta em "Todas" baixava outros 380 KB. Com 300 clientes e 600
ordens no banco, medido, o corpo da resposta era este:

    <tbody> com as linhas .................  76 KB
    clientesOSDados .......................  84 KB
    indiceOrdens ..........................  71 KB
    <script> da tela ......................  60 KB
    ordensServicoDados ....................  26 KB
    modais, cabeçalho, rodapé .............  63 KB

Dessas seis linhas, TRÊS não mudam quando o filtro muda: a lista de
clientes (que alimenta o autocompletar do formulário), o script da tela e
os modais. São 207 KB reenviados, analisados e descartados a cada toque
num cartão -- em rede de galpão, pelo celular, isso é a diferença entre
"filtrou" e "travou".

E não é só rede. Do lado do navegador, cada resposta dessas é um
documento inteiro para o `DOMParser` montar, mais a troca de todo o
`.ls-content`, mais os scripts da tela para reexecutar. O trabalho de
abrir uma tela nova, para trocar uma tabela.

O QUE MUDA, ENTÃO

Só quatro coisas: os cartões de contagem (qual está aceso), a faixa de
dinheiro, o painel da lista (tabela, paginação e o índice de busca) e o
JSON das linhas desenhadas. Cada um desses trechos é marcado no gabarito
com `data-ls-parte`, e é exatamente isso que este módulo devolve quando o
navegador pede `X-LS-Fragmento: lista`.

O gabarito do pedaço é o MESMO `{% include %}` que a página inteira usa.
Não existe uma segunda versão da tabela para manter em dia -- se
existisse, ela divergiria na primeira semana.

POR QUE O `Vary`

A mesma URL passa a ter duas respostas possíveis. Sem `Vary`, um cache
pelo caminho -- o do navegador, o de um proxy -- pode servir o pedaço
para quem pediu a página, e aí a tela abre sem cabeçalho e sem menu.
"""

from django.shortcuts import render

#: O navegador pede assim; ver `ls-soft-navigation.js`.
CABECALHO = "X-LS-Fragmento"
PEDIDO_LISTA = "lista"


def pediu_lista(request):
    """O navegador pediu só o pedaço da lista?"""
    return request.headers.get(CABECALHO, "").strip().lower() == PEDIDO_LISTA


def responder(request, gabarito, gabarito_lista, contexto):
    """Página inteira, ou só as partes -- conforme o que foi pedido."""
    if pediu_lista(request):
        resposta = render(request, gabarito_lista, contexto)
        resposta[CABECALHO] = PEDIDO_LISTA
    else:
        resposta = render(request, gabarito, contexto)
    resposta["Vary"] = ", ".join(
        parte for parte in [resposta.get("Vary", ""), CABECALHO] if parte
    )
    return resposta
