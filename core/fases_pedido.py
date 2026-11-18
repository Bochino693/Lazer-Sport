"""As fases do pedido da loja, como o cliente vê em Meus pedidos (seção 106).

O PEDIDO DO DONO. Depois de ver a linha do tempo dos orçamentos em Meus
pedidos (seção 104), ele disse: "em todos os pedidos devemos ter esse
faseamento, para o cliente conseguir ver tudo certinho até a entrega."

AS CINCO FASES, cada uma com o dia em que aconteceu (as datas que o
`Pedido.save()` grava quando a situação muda):

  1. Pedido feito    -- o dia e a hora da compra;
  2. Pagamento       -- "Aguardando Pix", "Boleto vence em 25/11",
                        "Cartão em análise"; pago: "Pago em 18/11 · Pix";
  3. Produção        -- "Começou em 18/11 · previsão 25/11" (o prazo em
                        dias úteis da seção 89), ou "Em preparação";
  4. Envio           -- "Saiu em 20/11 · Braspress · código ABC123", com o
                        "Rastrear"; na RETIRADA a fase é "Retirada":
                        "Pronto para retirada em 20/11", com o endereço;
  5. Entregue        -- "Entregue em 22/11" (ou "Retirado em 22/11").

O cancelado para (vermelho) na fase em que estava, com "Cancelado em
dd/mm"; o que vinha depois apaga. O desenho é o mesmo dos cartões de
orçamento (`oc-fases`, `is-feita`/`is-atual`/`is-parada`/`is-futura`).

Tudo sai dos campos do próprio pedido: montar as fases não consulta o
banco (Meus pedidos não fica mais lenta com mais pedidos).

Mora no `core`, e não no `sistema_interno` como as fases do orçamento: o
pedido é do site, e o `core` não depende do `sistema_interno`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils import timezone

from .producao import texto_dos_dias

#: O ícone de cada fase (todos no recorte do FontAwesome do site:
#: core/static/vendor/fontawesome-site/icones.txt).
ICONES_DAS_FASES = {
    "feito": "fa-bag-shopping",
    "pagamento": "fa-coins",
    "producao": "fa-industry",
    "envio": "fa-truck-fast",
    "retirada": "fa-store",
    "entrega": "fa-flag-checkered",
}

#: A fase de agora de cada situação (o índice na lista de cinco). O
#: finalizado tem todas feitas; o cancelado é decidido pelas datas.
FASE_DA_SITUACAO = {
    "aguardando_pagamento": 1,
    "pago": 2,
    "em_preparacao": 2,
    "saiu_entrega": 3,
    "finalizado": 5,
}

#: O chip do cartão: a situação do jeito que o cliente fala.
SITUACAO_PARA_O_CLIENTE = {
    "aguardando_pagamento": "Aguardando pagamento",
    "pago": "Pago",
    "em_preparacao": "Em preparação",
    "saiu_entrega": "Saiu para entrega",
    "finalizado": "Entregue",
    "cancelado": "Cancelado",
}

#: A escolha da equipe quando é a fábrica que leva (o caminhão da casa).
ENTREGA_PROPRIA = "Entrega própria"

#: O que a tela aceita: a coluna do banco é desse tamanho.
TAMANHO_TRANSPORTADORA = 120
TAMANHO_CODIGO = 60
TAMANHO_LINK = 500


@dataclass
class Fase:
    """Um passo da linha do tempo do pedido.

    `estado`: "feita" (verde, com o visto), "atual" (acesa, na cor do
    cartão), "parada" (vermelha: o cancelamento) ou "futura" (apagada).
    """

    chave: str
    nome: str
    icone: str
    estado: str = "futura"
    nota: str = ""


@dataclass
class AndamentoDoPedido:
    """Tudo o que o cartão do pedido mostra além do que já mostrava."""

    pedido: object
    fases: list[Fase] = field(default_factory=list)
    situacao_texto: str = ""
    #: A corrente parou (cancelado): o que vinha depois apaga.
    parou: bool = False
    #: O quadro do envio (só o pedido com frete, depois de sair):
    #: {"transportadora", "codigo", "link", "quando"}.
    envio: dict | None = None
    #: O quadro da retirada (pronto, esperando o cliente na fábrica).
    retirada_pronta: bool = False

    @property
    def fase_atual(self):
        return next((fase for fase in self.fases if fase.estado == "atual"), None)


def _dia(momento) -> str:
    """"18/11" (a linha do tempo é curta; o ano está no alto do cartão)."""
    if not momento:
        return ""
    if hasattr(momento, "hour"):
        momento = timezone.localtime(momento) if timezone.is_aware(momento) else momento
    return momento.strftime("%d/%m")


def _dia_e_hora(momento) -> str:
    if not momento:
        return ""
    if timezone.is_aware(momento):
        momento = timezone.localtime(momento)
    return momento.strftime("%d/%m às %H:%M")


def _com_data(texto, momento) -> str:
    """"Pago em 18/11" -- ou só "Pago", quando o dia não existe (pedido de antes)."""
    dia = _dia(momento)
    return f"{texto} em {dia}" if dia else texto


def forma_curta(pedido) -> str:
    """"Pix", "cartão 3x", "débito", "boleto" (o fim da nota do pagamento)."""
    forma = pedido.forma_pagamento or ""
    if forma == "pix":
        return "Pix"
    if forma == "credito":
        vezes = pedido.parcelas or 1
        return f"cartão {vezes}x" if vezes > 1 else "cartão"
    if forma == "debito":
        return "débito"
    if forma == "boleto":
        return "boleto"
    return ""


def _nota_do_pagamento_pendente(pedido, agora) -> str:
    if pedido.boleto_aberto:
        vencimento = pedido.boleto_vencimento
        if vencimento is None:
            return "Boleto gerado"
        if vencimento < agora:
            return f"Boleto venceu em {_dia(vencimento)}"
        return f"Boleto vence em {_dia(vencimento)}"
    if (pedido.mp_status or "") == "in_process":
        return "Cartão em análise"
    if pedido.mp_payment_id:
        return "Aguardando Pix"
    return "Esperando o pagamento"


def _nota_da_producao_atual(pedido) -> str:
    dias = pedido.prazo_producao_dias
    if dias == 0:
        return "Pronta entrega"
    inicio = pedido.inicio_da_producao
    if dias is not None and inicio is not None:
        nota = f"Começou em {_dia(inicio)}"
        previsao = pedido.previsao_producao
        if previsao is not None:
            nota += f" · previsão {_dia(previsao)}"
        return nota
    if pedido.status == "em_preparacao":
        dia = _dia(pedido.preparacao_em)
        return f"Em preparação desde {dia}" if dia else "Em preparação"
    return "Na fila da fábrica"


def _nota_do_envio(pedido) -> str:
    partes = [_com_data("Saiu", pedido.enviado_em)]
    if pedido.transportadora_envio:
        partes.append(pedido.transportadora_envio)
    if pedido.codigo_rastreio:
        partes.append(f"código {pedido.codigo_rastreio}")
    return " · ".join(partes)


def _indice_do_cancelamento(pedido) -> int:
    """Onde a corrente parou: a primeira fase sem o seu fato."""
    if pedido.pago_em is None:
        return 1
    if pedido.enviado_em is None:
        return 2
    # Saiu (ou ficou pronto) e não chegou: para no "Entregue". O cancelado
    # depois de entregue (a devolução) também para ali, no fim.
    return 4


def acompanhamento_do_pedido(pedido, *, agora=None) -> AndamentoDoPedido:
    """As fases do pedido, pelo que de fato aconteceu com ele."""
    agora = agora or timezone.now()
    retirada = pedido.tipo_envio == "retirada"
    status = pedido.status
    cancelado = status == "cancelado"

    feito = Fase("feito", "Pedido feito", ICONES_DAS_FASES["feito"])
    pagamento = Fase("pagamento", "Pagamento", ICONES_DAS_FASES["pagamento"])
    producao = Fase("producao", "Produção", ICONES_DAS_FASES["producao"])
    if retirada:
        envio = Fase("envio", "Retirada", ICONES_DAS_FASES["retirada"])
    else:
        envio = Fase("envio", "Envio", ICONES_DAS_FASES["envio"])
    entrega = Fase("entrega", "Retirado" if retirada else "Entregue", ICONES_DAS_FASES["entrega"])
    fases = [feito, pagamento, producao, envio, entrega]

    # As notas de cada fase, pelo fato dela (a fase de agora se acende depois).
    feito.nota = _dia_e_hora(pedido.criacao)

    if pedido.pago_em is not None or status in pedido.SITUACOES_PAGAS:
        forma = forma_curta(pedido)
        pagamento.nota = _com_data("Pago", pedido.pago_em) + (f" · {forma}" if forma else "")
    elif status == "aguardando_pagamento":
        pagamento.nota = _nota_do_pagamento_pendente(pedido, agora)

    if status in ("pago", "em_preparacao"):
        producao.nota = _nota_da_producao_atual(pedido)
    elif status in ("saiu_entrega", "finalizado") or (cancelado and pedido.enviado_em):
        producao.nota = _com_data("Pronta", pedido.enviado_em)
    elif status == "aguardando_pagamento" and pedido.prazo_producao_dias is not None:
        dias = pedido.prazo_producao_dias
        producao.nota = "Pronta entrega" if dias == 0 else f"{texto_dos_dias(dias).capitalize()} após o pagamento"

    if retirada:
        if status == "saiu_entrega":
            envio.nota = _com_data("Pronto para retirada", pedido.enviado_em)
        elif status == "finalizado" or (cancelado and pedido.enviado_em):
            envio.nota = _com_data("Pronto", pedido.enviado_em)
        elif not cancelado:
            envio.nota = "Na fábrica, em São Paulo"
    elif status in ("saiu_entrega", "finalizado") or (cancelado and pedido.enviado_em):
        envio.nota = _nota_do_envio(pedido)

    if status == "finalizado" or (cancelado and pedido.entregue_em):
        entrega.nota = _com_data("Retirado" if retirada else "Entregue", pedido.entregue_em)

    # OS ESTADOS: o que veio antes da fase de agora está feito.
    if cancelado:
        parada = _indice_do_cancelamento(pedido)
        for indice, fase in enumerate(fases):
            if indice < parada:
                fase.estado = "feita"
            elif indice == parada:
                fase.estado = "parada"
                fase.nota = _com_data("Cancelado", pedido.cancelado_em)
    else:
        atual = FASE_DA_SITUACAO.get(status, 1)
        for indice, fase in enumerate(fases):
            if indice < atual:
                fase.estado = "feita"
            elif indice == atual:
                fase.estado = "atual"

    situacao = SITUACAO_PARA_O_CLIENTE.get(status, pedido.get_status_display())
    if retirada and status == "saiu_entrega":
        situacao = "Pronto para retirada"
    elif retirada and status == "finalizado":
        situacao = "Retirado"

    quadro_do_envio = None
    if not retirada and status in ("saiu_entrega", "finalizado") and (
        pedido.transportadora_envio or pedido.codigo_rastreio or pedido.link_rastreio
    ):
        quadro_do_envio = {
            "transportadora": pedido.transportadora_envio,
            "codigo": pedido.codigo_rastreio,
            "link": pedido.link_rastreio,
            "quando": _dia(pedido.enviado_em),
            "propria": pedido.transportadora_envio == ENTREGA_PROPRIA,
        }

    return AndamentoDoPedido(
        pedido=pedido,
        fases=fases,
        situacao_texto=situacao,
        parou=cancelado,
        envio=quadro_do_envio,
        retirada_pronta=retirada and status == "saiu_entrega",
    )


# ----------------------------------------------------------------------
# O ENVIO QUE A EQUIPE INFORMA NO PAINEL
# ----------------------------------------------------------------------
def _limpo(texto) -> str:
    return " ".join(str(texto or "").split())


_URL = URLValidator(schemes=["http", "https"])


def ler_envio(dados) -> dict:
    """Confere o que a equipe digitou e devolve os campos do pedido.

    A transportadora é obrigatória (ou "Entrega própria"); o código pode
    entrar depois (há transportadora que só dá o número no dia seguinte);
    o link é opcional, mas tem de ser um endereço da internet -- é ele que
    vira o botão "Rastrear" na tela do cliente. Levanta ValueError com a
    frase da tela.
    """
    transportadora = _limpo(dados.get("transportadora"))
    codigo = _limpo(dados.get("codigo_rastreio"))
    link = str(dados.get("link_rastreio") or "").strip()

    if not transportadora:
        raise ValueError("Escolha a transportadora (ou “Entrega própria”).")
    if len(transportadora) > TAMANHO_TRANSPORTADORA:
        raise ValueError(f"O nome da transportadora passa de {TAMANHO_TRANSPORTADORA} letras.")
    if len(codigo) > TAMANHO_CODIGO:
        raise ValueError(f"O código de rastreio passa de {TAMANHO_CODIGO} letras.")
    if link:
        if "://" not in link:
            link = f"https://{link}"
        if len(link) > TAMANHO_LINK:
            raise ValueError("O link de rastreio é comprido demais.")
        try:
            _URL(link)
        except ValidationError:
            raise ValueError("O link de rastreio precisa ser um endereço da internet (https://...).") from None
    return {
        "transportadora_envio": transportadora,
        "codigo_rastreio": codigo,
        "link_rastreio": link,
    }
