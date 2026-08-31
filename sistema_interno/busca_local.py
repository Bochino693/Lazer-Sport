"""O índice que deixa a busca das listas acontecer no aparelho.

A busca das telas de lista era um formulário GET: cada palavra digitada
só valia depois de apertar a lupa, e a tela inteira recarregava. Aqui se
monta o que o navegador precisa para responder sozinho -- número do
registro e um texto já sem acento, pronto para comparar.

DUAS COISAS IMPORTAM NESTE FORMATO. Ele é minúsculo (duas chaves de uma
letra por registro, e nenhum dado que a tela já não mostre), porque viaja
junto de toda página da lista. E ele cobre o FILTRO INTEIRO, não só a
página desenhada: é isso que permite ao navegador dizer "existe, mas está
na página seguinte" em vez de mentir "nada encontrado".
"""

import unicodedata


def sem_acento(texto):
    """Mesma normalização que o navegador aplica no que é digitado.

    As duas pontas precisam concordar: quem procura "orcamento" tem de
    achar "orçamento", e quem procura "JOÃO" tem de achar "joao".
    """
    if not texto:
        return ""
    cru = unicodedata.normalize("NFD", str(texto))
    limpo = "".join(letra for letra in cru if not unicodedata.combining(letra))
    return limpo.casefold().strip()


def montar_indice(registros):
    """`registros` é um iterável de (identificador, pedaços de texto).

    Os pedaços vazios somem, e o que sobra vira uma única linha de texto:
    procurar é um `indexOf` sobre ela, e não uma volta por campo.
    """
    indice = []
    for identificador, pedacos in registros:
        texto = " ".join(
            sem_acento(pedaco) for pedaco in pedacos if pedaco not in (None, "")
        )
        indice.append({"i": str(identificador), "t": " ".join(texto.split())})
    return indice
