"""AS ETAPAS DO PEDIDO, PARA A EQUIPE (LEIA-ME-V10, seção 117).

O dono: "revise todo o sistema e deixe fluido, com as etapas bem definidas
e claras para seguir". O cliente já via, em Meus pedidos, seis fases
(Proposta -> Aprovação -> Contrato assinado -> Pagamento -> Produção ->
Entregue); a janela do orçamento no painel mostrava outra régua, de quatro
passos (Aprovado -> Assinatura -> Pagamento -> Venda), com outras palavras.
Duas réguas para o mesmo pedido confundem quem atende pelo telefone.

Agora é uma régua só. As fases e o estado de cada uma ("feita", "atual",
"parada", "futura") vêm de `codigo_orcamento.acompanhamento` -- a mesma
regra que o cliente lê, sem uma segunda cópia. O que muda é a voz: o
cliente lê "Pronto para você assinar"; a equipe lê o que ELA faz agora, e
com quem está a vez (Comercial, Financeiro, Produção):

  * `etapas(orcamento, user)` -> `EtapasDoPedido`: as seis fases com a nota
    da equipe e o PRÓXIMO PASSO (o texto, quem faz e o botão que leva lá);
  * a parte `partes/etapas_do_pedido.html` desenha; a janela do orçamento
    pede o HTML pronto (`orcamento_etapas`) e a tela do contrato já nasce
    com ele (e o troca quando o cliente assina).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal

from django.urls import reverse

URLCONF = "sistema_interno.urls"

#: O ícone de cada fase no painel (Bootstrap Icons).
ICONES = {
    "proposta": "bi-file-earmark-text",
    "aprovacao": "bi-patch-check",
    "termo": "bi-pen",
    "pagamento": "bi-wallet2",
    "producao": "bi-tools",
    "entrega": "bi-truck",
}

#: Com quem está a vez em cada fase (a função que resolve).
QUEM = {
    "proposta": "Comercial",
    "aprovacao": "Comercial",
    "termo": "Comercial",
    "pagamento": "Financeiro",
    "producao": "Produção",
    "entrega": "Produção",
}


@dataclass
class Etapa:
    chave: str
    nome: str
    estado: str
    nota: str
    icone: str
    numero: int


@dataclass
class ProximoPasso:
    texto: str
    detalhe: str = ""
    quem: str = ""
    #: "ok" (verde: nada a fazer), "vez" (a fase de agora), "alerta" (parou)
    tom: str = "vez"
    icone: str = "bi-arrow-right-circle"
    acao: str = ""
    url: str = ""
    #: o id do quadro da janela do orçamento que o botão acende, quando a
    #: tela tem esse quadro (sem ele, o botão segue o `url`)
    alvo: str = ""


@dataclass
class EtapasDoPedido:
    lista: list[Etapa] = field(default_factory=list)
    proximo: ProximoPasso | None = None
    url: str = ""
    #: muda quando alguma coisa na régua muda (a janela não redesenha à toa)
    marca: str = ""

    @property
    def feitas(self):
        return sum(1 for etapa in self.lista if etapa.estado == "feita")


def _moeda(valor) -> str:
    valor = Decimal(valor or 0).quantize(Decimal("0.01"))
    inteiro, centavos = f"{valor:.2f}".split(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    # espaço que não quebra: "R$" e o número nunca ficam em linhas diferentes
    return f"R$\u00a0{inteiro},{centavos}"


def _url(nome, *args):
    return reverse(nome, args=list(args), urlconf=URLCONF)


def _nota_da_equipe(fase, orcamento, acomp, documento):
    """A nota da fase na voz da equipe (a do cliente fala com o cliente)."""
    from .models import Orcamento

    Status = Orcamento.Status
    chave = fase.chave
    if chave == "proposta" and orcamento.status == Status.RASCUNHO:
        return "Em montagem"
    if chave == "aprovacao":
        if orcamento.status == Status.EM_NEGOCIACAO:
            return "O cliente pediu ajustes"
        if orcamento.status == Status.AGUARDANDO_RESPOSTA:
            validade = orcamento.validade
            return f"Cliente responde até {validade:%d/%m}" if validade else "Esperando o cliente"
        if orcamento.status == Status.RASCUNHO:
            return "Depois do envio"
    if chave == "termo" and fase.estado != "feita":
        from . import documento_assinatura as svc

        if orcamento.status != Status.APROVADO:
            return "Depois da aprovação"
        if documento is None:
            return "Gerar o contrato"
        if svc.aberto_agora(documento):
            return "O cliente está lendo agora"
        if fase.nota.startswith("Suspenso"):
            return "Suspenso"
        return "Esperando a assinatura"
    if chave == "pagamento":
        if orcamento.quitado:
            venda = f" · venda #{orcamento.venda_id}" if orcamento.venda_id else ""
            return (fase.nota or "Pago") + venda
        if orcamento.status != Status.APROVADO:
            return "Depois da aprovação"
        if acomp.percentual_pago:
            return f"{acomp.percentual_pago}% pago · faltam {_moeda(orcamento.saldo_pagamento)}"
        return f"A receber {_moeda(orcamento.saldo_pagamento or orcamento.total)}"
    if chave in ("producao", "entrega") and orcamento.status != Status.APROVADO and fase.estado != "feita":
        return ""
    return fase.nota


def _proximo(orcamento, acomp, documento, acesso, tela) -> ProximoPasso:
    """O que fazer agora, quem faz, e o botão que leva lá."""
    from . import documento_assinatura as svc
    from .models import Orcamento

    Status = Orcamento.Status
    fases = {fase.chave: fase for fase in acomp.fases}
    janela = f"{_url('orcamentos_inner')}?q={orcamento.pk}&editar={orcamento.pk}"
    prazo = svc.prazo_do_link()

    # PAROU: recusada, vencida, trocada por outra versão.
    if orcamento.status == Status.RECUSADO:
        return ProximoPasso(
            "O cliente recusou esta proposta.",
            "Se ele mudar de ideia, faça uma nova versão com o que ele pediu.",
            quem=QUEM["aprovacao"], tom="alerta", icone="bi-x-octagon",
        )
    if orcamento.status == Status.SUBSTITUIDO:
        return ProximoPasso(
            "Esta versão foi trocada por outra.",
            "Abra a versão mais nova: é ela que anda.",
            quem=QUEM["aprovacao"], tom="alerta", icone="bi-clock-history",
        )
    if fases["aprovacao"].estado == "parada":
        return ProximoPasso(
            "A validade da proposta acabou.",
            "Faça uma nova versão com o preço de hoje e envie de novo.",
            quem=QUEM["aprovacao"], tom="alerta", icone="bi-calendar-x",
        )

    atual = acomp.fase_atual
    if atual is None:
        entrega = fases["entrega"]
        return ProximoPasso(
            "Pedido concluído.", entrega.nota or "Entregue ao cliente.",
            tom="ok", icone="bi-check2-circle",
        )

    chave = atual.chave
    quem = QUEM[chave]
    if chave == "proposta":
        return ProximoPasso(
            "Termine a proposta e envie ao cliente.",
            "Confira itens, valores e validade; no envio, o cliente recebe o link para aprovar.",
            quem=quem, icone="bi-send",
        )
    if chave == "aprovacao":
        if orcamento.status == Status.EM_NEGOCIACAO:
            motivo = (orcamento.motivo_negociacao or "").strip()
            return ProximoPasso(
                "O cliente pediu ajustes: faça a nova versão.",
                f"O pedido dele: “{motivo[:140]}”." if motivo else "Ajuste a proposta e envie a versão nova.",
                quem=quem, icone="bi-arrow-repeat",
            )
        validade = f" A proposta vale até {orcamento.validade:%d/%m/%Y}." if orcamento.validade else ""
        return ProximoPasso(
            "Esperando o cliente aprovar.",
            "Ele aprova pelo link da proposta ou em Meus pedidos, no site." + validade,
            quem=quem, icone="bi-hourglass-split",
        )
    if chave == "termo":
        pode = acesso.get("orcamentos_editar_comercial")
        # na tela do contrato, o cartão (o QR, o link) é o próprio botão
        url = _url("documento_assinatura_inner", orcamento.pk) if pode and tela != "contrato" else ""
        if documento is None:
            texto = "Gere o contrato e passe para o cliente assinar."
            detalhe = (
                f"Mostre o QR na tela ou mande o link pelo WhatsApp (vale {prazo}). "
                "O cliente também assina sozinho em Meus pedidos."
            )
            acao = "Gerar o contrato"
        elif svc.aberto_agora(documento):
            texto = "O cliente está com o contrato aberto."
            detalhe = (
                f"Ele assina naquele aparelho enquanto o link valer ({prazo}), "
                "sem link novo. A régua anda sozinha quando ele assinar."
            )
            acao = "Acompanhar"
        elif atual.nota.startswith("Suspenso"):
            texto = "O contrato está suspenso."
            detalhe = "O orçamento deixou de estar aprovado depois de o contrato sair: confira antes de seguir."
            acao = "Ver o contrato"
        else:
            texto = "Passe o contrato para o cliente assinar."
            detalhe = (
                f"Mostre o QR ou mande o link pelo WhatsApp: vale {prazo}, "
                "e o cliente assina quando puder dentro desse prazo."
            )
            acao = "Abrir o QR e o link"
        return ProximoPasso(
            texto, detalhe, quem=quem, icone="bi-pen",
            acao=acao if url else "", url=url, alvo="orcamentoDocumentoAssinatura" if url else "",
        )
    if chave == "pagamento":
        pode = acesso.get("orcamentos_editar_financeiro")
        saldo = _moeda(orcamento.saldo_pagamento or orcamento.total)
        return ProximoPasso(
            f"Registre o pagamento: faltam {saldo}.",
            "Ao chegar a 100%, o pedido vira venda sozinho e entra na fila da fábrica.",
            quem=quem, icone="bi-wallet2",
            # de fora da janela (a tela do contrato), o link já abre no quadro do pagamento
            acao="Registrar pagamento" if pode else "",
            url=f"{janela}&ir=orcamentoPagamentoResumo" if pode else "",
            alvo="orcamentoPagamentoResumo" if pode else "",
        )
    pode_lista = acesso.get("lista_montagem")
    lista = _url("lista_montagem") if pode_lista else ""
    if chave == "producao":
        return ProximoPasso(
            "A fábrica está fazendo.",
            (atual.nota or "Na fila de produção") + ". Cada etapa feita na Lista de montagem anda aqui também.",
            quem=quem, icone="bi-tools",
            acao="Abrir a lista de montagem" if lista else "", url=lista,
        )
    return ProximoPasso(
        "Pronto: combine a entrega com o cliente.",
        "Depois da entrega, marque “Entregue” na Lista de montagem (ou conclua a ordem de serviço).",
        quem=quem, icone="bi-truck",
        acao="Abrir a lista de montagem" if lista else "", url=lista,
    )


def etapas(orcamento, user=None, *, tela="janela") -> EtapasDoPedido:
    """A régua do pedido para a equipe: seis fases e o próximo passo.

    `tela`: "janela" (a do orçamento) ou "contrato" (a do documento, onde o
    cartão do QR já é a ação da fase do contrato).
    """
    from .codigo_orcamento import acompanhamento
    from .permissoes import capacidades

    acomp = acompanhamento(orcamento)
    documento = acomp.documento
    acesso = capacidades(user) if user is not None else {}
    lista = [
        Etapa(
            chave=fase.chave,
            nome=fase.nome,
            estado=fase.estado,
            nota=_nota_da_equipe(fase, orcamento, acomp, documento),
            icone=ICONES[fase.chave],
            numero=numero,
        )
        for numero, fase in enumerate(acomp.fases, start=1)
    ]
    proximo = _proximo(orcamento, acomp, documento, acesso, tela)
    marca = "|".join(f"{e.chave}:{e.estado}:{e.nota}" for e in lista) + f"|{proximo.texto}"
    return EtapasDoPedido(
        lista=lista,
        proximo=proximo,
        url=_url("orcamento_etapas", orcamento.pk),
        marca=hashlib.md5(marca.encode(), usedforsecurity=False).hexdigest()[:12],
    )
