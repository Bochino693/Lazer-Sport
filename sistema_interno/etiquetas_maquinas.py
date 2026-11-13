"""As etiquetas por máquina: do pedido, do orçamento e da venda, em folhas A4.

O PEDIDO DO DONO. "Devemos imprimir a etiqueta, que já temos, a partir de
um orçamento ou pedido -- ponha nos dois e na venda --, setando quantas
cópias por máquina nós queremos, usando sempre as folhas A4, para imprimir
a quantidade que der e ir passando de folha."

A ETIQUETA É A MESMA. O desenho é o da tela de Etiquetas (views_etiquetas,
interno_modern.css: preto no branco, a moldura, o "Frágil" em faixa, o
destino e o remetente). O que muda é a ORIGEM: em vez de digitar, cada
máquina do pedido vira etiquetas, e o conteúdo é a própria máquina.

CÓPIAS POR MÁQUINA. Cada linha (uma máquina, N unidades) recebe "quantas
cópias por máquina": 2 unidades x 3 cópias = 6 etiquetas -- a máquina que
viaja em 3 volumes sai com "Volume 1/3, 2/3, 3/3", e a segunda unidade
também. O padrão é 1 cópia: uma etiqueta por unidade.

A FOLHA A4. A etiqueta tem os dois tamanhos que já existiam: um quarto de
folha (A6, 4 por A4, o padrão) e meia folha (A5, 2 por A4). As folhas são
montadas AQUI, e não deixadas ao navegador: 15 etiquetas em A6 são 4
folhas (4 + 4 + 4 + 3), cada uma do tamanho exato de um A4, com a quebra
de página entre elas. O navegador que decidisse sozinho cortaria uma
etiqueta no meio da página ou deixaria meia folha em branco.

NADA É GRAVADO, como na tela de Etiquetas: a etiqueta é papel.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from django.utils import timezone

from .rotas import texto_endereco

#: Quantas etiquetas cabem numa folha A4, por tamanho de etiqueta.
POR_FOLHA = {"a6": 4, "a5": 2}
TAMANHOS = (
    ("a6", "Um quarto (A6)", "4 por folha A4"),
    ("a5", "Meia folha (A5)", "2 por folha A4"),
)
TAMANHO_PADRAO = "a6"

#: Teto de cópias por máquina e de etiquetas por impressão. 99 cópias de
#: uma máquina já é engano de digitação; 600 etiquetas são 150 folhas --
#: acima disso a página fica pesada demais para o navegador do galpão.
COPIAS_MAXIMAS = 99
ETIQUETAS_MAXIMAS = 600


def folhas_necessarias(total: int, por_folha: int) -> int:
    """15 etiquetas, 4 por folha: 4 folhas. Zero etiquetas: zero folhas."""
    if total <= 0:
        return 0
    return math.ceil(total / por_folha)


def em_folhas(etiquetas: list, por_folha: int) -> list[list]:
    """As etiquetas em pedaços do tamanho da folha, na ordem."""
    return [
        etiquetas[inicio:inicio + por_folha]
        for inicio in range(0, len(etiquetas), por_folha)
    ]


@dataclass(frozen=True)
class Maquina:
    """Uma linha do pedido ou do orçamento: o que vira etiqueta."""

    id: int
    nome: str
    quantidade: int

    def como_dado(self):
        return {"id": self.id, "nome": self.nome, "quantidade": self.quantidade}


# ----------------------------------------------------------------------
# a origem: pedido, orçamento ou venda
# ----------------------------------------------------------------------

def _nome_do_cliente_do_site(pedido) -> str:
    """O nome de quem recebe -- o mesmo da tela de Pedidos do painel."""
    perfil = pedido.cliente if pedido.cliente_id else None
    if perfil is None:
        return "Cliente do site"
    if (perfil.nome_completo or "").strip():
        return perfil.nome_completo.strip()
    conta = perfil.user if perfil.user_id else None
    if conta is not None:
        return conta.get_full_name() or conta.username
    return "Cliente do site"


#: O que a etiqueta do pedido do site diz sobre o envio. O site deixou de
#: cobrar frete: o pedido é RETIRADO NA FÁBRICA, e o frete, quando há, é
#: combinado pelo cliente com a transportadora dele -- que leva a caixa com
#: esta etiqueta. Nada aqui supõe um valor de frete.
ENVIO_RETIRADA = "Retirada na fábrica · frete por conta do cliente"


def ficha_do_pedido(pedido) -> dict:
    perfil = pedido.cliente if pedido.cliente_id else None
    # O endereço que o pedido guardou, quando guardou (o pedido antigo, com
    # frete, guarda; o de retirada pode não ter nenhum). Sem endereço, a
    # etiqueta fica com o nome, o telefone e o aviso da retirada.
    endereco = texto_endereco(pedido)
    return {
        "tipo": "pedido",
        "id": pedido.pk,
        "titulo": f"Pedido #{pedido.pk}",
        "referencia": f"Pedido #{pedido.pk}",
        "nome": _nome_do_cliente_do_site(pedido),
        "endereco": endereco,
        "contato": (getattr(perfil, "telefone", "") or "") if perfil else "",
        "envio": "" if pedido.tipo_envio == "frete" else ENVIO_RETIRADA,
        "maquinas": [
            Maquina(item.pk, item.nome_item, max(int(item.quantidade or 1), 1))
            for item in pedido.itens.all()
        ],
        "origem": pedido,
        "pronta": pedido.pago,
        "motivo": "" if pedido.pago else (
            "A etiqueta é do pedido pago: este ainda espera o pagamento."
            if pedido.status == "aguardando_pagamento"
            else "Pedido cancelado não vira etiqueta."
        ),
    }


def ficha_do_orcamento(orcamento) -> dict:
    endereco = (
        orcamento.cliente.endereco_principal
        if orcamento.cliente_id and orcamento.cliente else None
    )
    aprovado = orcamento.status == orcamento.Status.APROVADO
    return {
        "tipo": "orcamento",
        "id": orcamento.pk,
        "titulo": f"Orçamento nº {orcamento.numero_documento}",
        "referencia": f"Orçamento nº {orcamento.numero_documento}",
        "nome": orcamento.destinatario,
        "endereco": texto_endereco(endereco),
        "contato": orcamento.whatsapp_destinatario,
        # O orçamento diz o envio no texto dele ("A combinar", "Retirada").
        "envio": (orcamento.forma_envio or "").strip(),
        "maquinas": [
            Maquina(item.pk, item.descricao, max(int(item.quantidade or 1), 1))
            for item in orcamento.itens.all()
        ],
        "origem": orcamento,
        "pronta": aprovado,
        "motivo": "" if aprovado else (
            "A etiqueta é da proposta aprovada. Esta está como "
            f"“{orcamento.get_status_display()}”."
        ),
    }


def ficha_da_venda(venda) -> dict | None:
    """A venda imprime pelas máquinas de onde veio, com o número dela."""
    origem = venda.origem_objeto
    if origem is None:
        return None
    if venda.pedido_id:
        ficha = ficha_do_pedido(origem)
    else:
        ficha = ficha_do_orcamento(origem)
    ficha["titulo"] = f"Venda #{venda.pk} · {ficha['titulo']}"
    ficha["referencia"] = f"{ficha['referencia']} · Venda #{venda.pk}"
    ficha["venda"] = venda.pk
    return ficha


# ----------------------------------------------------------------------
# as cópias e as etiquetas
# ----------------------------------------------------------------------

def ler_copias(valores, maquinas) -> dict[int, int]:
    """As cópias por máquina que vieram da tela ("12:3", uma por linha).

    Máquina que não é desta origem é ignorada (o número veio de outra
    aba, ou foi digitado). Sem nada, vale o padrão: uma cópia por máquina.
    """
    conhecidas = {maquina.id for maquina in maquinas}
    copias = {}
    for valor in valores or ():
        chave, _, quantas = str(valor).partition(":")
        if not (chave.strip().isdigit() and quantas.strip().isdigit()):
            continue
        item_id = int(chave)
        if item_id in conhecidas:
            copias[item_id] = min(int(quantas), COPIAS_MAXIMAS)
    if not valores:
        copias = {maquina.id: 1 for maquina in maquinas}
    return copias


def contar(maquinas, copias) -> int:
    return sum(maquina.quantidade * copias.get(maquina.id, 0) for maquina in maquinas)


def data_da_producao(origem, hoje=None):
    """A data que a etiqueta mostra em "Produção".

    A previsão de pronto, quando a equipe informou o prazo; sem ela, o dia
    da impressão -- quem imprime a etiqueta da máquina normalmente acabou
    de terminá-la. O rótulo diz qual das duas é.
    """
    previsao = getattr(origem, "previsao_producao", None)
    if previsao is not None:
        return "Pronto em", previsao
    return "Emitida em", hoje or timezone.localdate()


def montar_etiquetas(ficha, copias, hoje=None) -> list[dict]:
    """Uma etiqueta por unidade de cada máquina e por cópia, na ordem."""
    rotulo, data = data_da_producao(ficha["origem"], hoje)
    etiquetas = []
    for maquina in ficha["maquinas"]:
        volumes = copias.get(maquina.id, 0)
        if not volumes:
            continue
        for unidade in range(1, maquina.quantidade + 1):
            for volume in range(1, volumes + 1):
                etiquetas.append({
                    "maquina": maquina.nome,
                    "unidade": unidade,
                    "unidades": maquina.quantidade,
                    "volume": volume,
                    "volumes": volumes,
                    "nome": ficha["nome"],
                    "endereco": ficha["endereco"],
                    "contato": ficha["contato"],
                    "envio": ficha.get("envio", ""),
                    "referencia": ficha["referencia"],
                    "producao_rotulo": rotulo,
                    "producao_data": data,
                })
    return etiquetas
