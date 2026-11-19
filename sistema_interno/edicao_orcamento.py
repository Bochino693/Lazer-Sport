"""A proposta muda NO LUGAR até a assinatura (LEIA-ME-V10, seção 123).

O PEDIDO DO DONO: "minha usuária fechou um contrato de um jeito, porém teve
que inserir mais itens e deu divergências, o sistema deve permitir
alterações até a assinatura, se assinou não muda mais. mas enquanto isso
podemos mudar sem erros".

O QUE ACONTECIA. A janela só gravava por cima do rascunho (e da proposta
salva que ainda não tinha saído). A aprovada que precisava de mais um item
tinha de virar a versão 2 ("Refazer proposta"): a versão 1 ficava
"substituída", o contrato dela suspenso, a 2 precisava ser aprovada de novo
-- e o pagamento, a lista de montagem e a régua ficavam apontando para
versões diferentes.

O QUE ACONTECE AGORA (as três peças daqui):

  * `trava(orcamento)` -- por que a janela NÃO grava, em palavras de tela
    (título, texto e o botão que resolve), ou None. É a mesma regra de
    `Orcamento.pode_editar_formulario`: assinado, não muda mais; a que
    liberou uma O.S. continua congelada com ela; recusada, expirada e
    substituída são história (o caminho delas é "Refazer proposta").
  * `Antes.do_orcamento(...)` -- o retrato do que importa ANTES de gravar
    (total, itens e o que vai no contrato), lido sem consulta a mais.
  * `acompanhar(...)` -- depois de gravar, o que deriva da proposta anda
    junto, na mesma transação: o pagamento refeito contra o total novo (e a
    venda do 100%), a lista de montagem com as máquinas novas e sem as que
    saíram, o contrato que espera assinatura REFEITO com os itens novos (os
    links velhos morrem na hora) e a linha do histórico dizendo o que
    mudou. Devolve a janela que a tela mostra ("Contrato refeito...").
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import DocumentoAssinatura, Orcamento

logger = logging.getLogger(__name__)

URLCONF = "sistema_interno.urls"

#: O texto que a janela mostra quando o contrato é refeito (o dono leu este).
TEXTO_CONTRATO_REFEITO = (
    "Contrato refeito com os itens novos; os links anteriores deixaram de "
    "valer — gere/mande o link de novo."
)


def _moeda(valor) -> str:
    from core.formatos import dinheiro

    return dinheiro(valor, prefixo="R$")


def _url(nome, *args):
    return reverse(nome, args=list(args), urlconf=URLCONF)


# ======================================================================
# 1. A TRAVA: por que a janela não grava (ou None)
# ======================================================================
@dataclass
class Trava:
    chave: str
    titulo: str
    texto: str
    icone: str = "info"
    acao: dict | None = None

    def como_dict(self):
        return {
            "chave": self.chave,
            "titulo": self.titulo,
            "texto": self.texto,
            "icone": self.icone,
            "acao": self.acao,
        }


def documento_assinado(orcamento):
    """O contrato assinado do orçamento (ou None), numa consulta no máximo.

    A lista já trouxe o documento de cada linha (`documento_assinatura`,
    posto pela view): quando ele veio, a resposta sai dele.
    """
    if not orcamento.pk:
        return None
    if "documento_assinatura" in orcamento.__dict__:
        documento = orcamento.__dict__["documento_assinatura"]
        if documento is not None and documento.situacao == DocumentoAssinatura.Situacao.ASSINADO:
            return documento
        return None
    return (
        DocumentoAssinatura.objects
        .filter(orcamento=orcamento, situacao=DocumentoAssinatura.Situacao.ASSINADO)
        .only("id", "orcamento_id", "situacao", "assinante_nome", "assinado_em")
        .first()
    )


def texto_do_assinado(documento) -> str:
    quem = (documento.assinante_nome or "").strip() or "o cliente"
    quando = (
        f" em {timezone.localtime(documento.assinado_em):%d/%m}" if documento.assinado_em else ""
    )
    return (
        f"Contrato assinado por {quem}{quando}: este pedido não muda mais. "
        "Se a compra mudou, fale com a Gestão."
    )


def trava(orcamento) -> Trava | None:
    """Por que esta proposta não muda pela janela -- ou None, se muda.

    A MESMA regra de `Orcamento.pode_editar_formulario` (há teste que
    confere as duas), com as palavras da janela de app e o botão que
    resolve.
    """
    S = Orcamento.Status
    if not orcamento.pk:
        return None
    if orcamento.status == S.SUBSTITUIDO:
        return Trava(
            "substituida", "Versão substituída",
            f"Esta é a versão {orcamento.versao}, trocada por uma mais nova. Para "
            "mudar o pedido, abra a versão que está valendo.",
            icone="info",
        )
    if orcamento.status in (S.RECUSADO, S.EXPIRADO):
        recusada = orcamento.status == S.RECUSADO
        acao = (
            {"rotulo": "Refazer proposta", "chave": "refazer", "id": orcamento.pk}
            if orcamento.pode_refazer else None
        )
        return Trava(
            "encerrada",
            "Proposta recusada" if recusada else "Proposta expirada",
            (
                "O cliente recusou esta proposta: ela fica no histórico como foi. "
                if recusada else
                "Esta proposta passou da validade e fica no histórico como foi. "
            ) + "Para mudar, faça a nova versão (“Refazer proposta”).",
            icone="alerta", acao=acao,
        )
    if orcamento.status not in Orcamento.EDITAVEIS:
        return Trava("historia", "Só para consulta", "Esta proposta é história e não muda mais.")
    if orcamento.status == S.RASCUNHO:
        return None
    assinado = documento_assinado(orcamento)
    if assinado is not None:
        return Trava(
            "assinado", "Contrato assinado", texto_do_assinado(assinado),
            icone="arquivo",
            acao={"rotulo": "Ver contrato", "url": _url("documento_assinatura_inner", orcamento.pk)},
        )
    if hasattr(orcamento, "ordem_servico"):
        ordem = orcamento.ordem_servico
        numero = getattr(ordem, "numero_documento", "") or f"#{ordem.pk}"
        return Trava(
            "os", "Proposta com O.S.",
            f"Esta proposta já liberou a O.S. {numero} e fica congelada junto com "
            "ela (a regra de sempre): mude o que for preciso na Ordem de Serviço.",
            icone="info",
            acao={"rotulo": "Abrir a O.S.", "url": _url("ordens_servico_inner") + f"?q={ordem.pk}"},
        )
    return None


def aviso_da_janela(orcamento, documento_janela=None) -> str:
    """A nota do alto da janela que GRAVA: o que salvar vai mexer junto.

    Não é erro nem trava -- é o "olha, isto anda junto" antes de salvar.
    `documento_janela` é o atalho do contrato que a janela já recebe
    (`OrcamentosInnerView.documento_da_janela`): nada é consultado aqui.
    """
    S = Orcamento.Status
    if not orcamento.pk or orcamento.status == S.RASCUNHO:
        return ""
    partes = []
    if orcamento.status == S.APROVADO:
        situacao = (documento_janela or {}).get("situacao")
        if situacao in ("aguardando", "suspenso"):
            partes.append(
                "Aprovada, com o contrato esperando a assinatura: mudar itens, valores "
                "ou condições refaz o contrato, e os links que já saíram deixam de valer."
            )
        else:
            partes.append("Aprovada: dá para mudar até o cliente assinar o contrato.")
        if (orcamento.valor_pago or Decimal("0.00")) > 0:
            partes.append("O pagamento já registrado é refeito contra o total novo.")
    elif orcamento.enviado_em:
        partes.append(
            "O cliente já recebeu esta proposta: ao salvar, o link dele mostra a versão nova."
        )
    return " ".join(partes)


# ======================================================================
# 2. O RETRATO DE ANTES (sem consulta a mais)
# ======================================================================
def total_com_itens(orcamento, itens) -> Decimal:
    """O total do orçamento com ESTA lista de itens, sem ir ao banco.

    A conta é a do modelo (`Orcamento.total`: itens + frete − desconto, ou
    o valor final combinado): a lista entra no lugar da relação só durante
    a leitura.
    """
    guardado = getattr(orcamento, "_prefetched_objects_cache", None)
    orcamento._prefetched_objects_cache = {**(guardado or {}), "itens": list(itens)}
    try:
        return orcamento.total
    finally:
        if guardado is None:
            del orcamento._prefetched_objects_cache
        else:
            orcamento._prefetched_objects_cache = guardado


def linhas_dos_itens(itens) -> tuple:
    """Os itens como o contrato e a produção os veem (na ordem gravada)."""
    return tuple(
        (
            (item.descricao or "").strip(), item.brinquedo_id, item.produto_id,
            item.peca_id, int(item.quantidade or 0), Decimal(item.valor_unitario or 0),
        )
        for item in sorted(itens, key=lambda i: (i.pk is None, i.pk or 0))
    )


def assinatura_do_contrato(orcamento, itens) -> tuple:
    """O que, mudando, muda o CONTRATO (e por isso o refaz).

    O cliente (cadastro, nome, contato, WhatsApp e e-mail), os itens, o
    frete, o desconto ou o valor final, a forma de pagamento (a Cláusula
    2ª), a forma de envio e as observações. A validade não entra: depois
    da aprovação ela não diz nada ao contrato.
    """
    return (
        orcamento.cliente_id, orcamento.nome_cliente, orcamento.contato,
        orcamento.whatsapp_cliente, orcamento.email_cliente,
        orcamento.forma_envio, orcamento.observacoes,
        orcamento.desconto, orcamento.frete, orcamento.valor_final,
        orcamento.forma_pagamento, linhas_dos_itens(itens),
    )


@dataclass
class Antes:
    status: str
    total: Decimal
    itens: tuple
    contrato: tuple
    enviada: bool

    @classmethod
    def do_orcamento(cls, orcamento, itens):
        itens = list(itens)
        return cls(
            status=orcamento.status,
            total=total_com_itens(orcamento, itens),
            itens=linhas_dos_itens(itens),
            contrato=assinatura_do_contrato(orcamento, itens),
            enviada=bool(orcamento.enviado_em),
        )


# ======================================================================
# 3. DEPOIS DE GRAVAR: o que deriva da proposta anda junto
# ======================================================================
@dataclass
class Resultado:
    """O que mudou junto com a proposta, para a janela e para o histórico."""

    janela_titulo: str = ""
    janela_texto: str = ""
    janela_nivel: str = "sucesso"
    janela_icone: str = ""
    acao: dict | None = None
    lista: list = field(default_factory=list)
    historico: list = field(default_factory=list)
    contrato_refeito: bool = False
    contrato_retirado: bool = False
    documento_novo: int | None = None
    venda: object = None
    montagem: dict = field(default_factory=dict)

    def janela(self):
        """A janela de app do resultado, ou None (aí basta o "Salvo.")."""
        if not (self.janela_titulo or self.lista):
            return None
        return {
            "titulo": self.janela_titulo or "Orçamento salvo",
            "texto": self.janela_texto,
            "nivel": self.janela_nivel,
            "icone": self.janela_icone or ("arquivo" if self.contrato_refeito else "salvo"),
            "lista": self.lista,
            "acao": self.acao,
        }

    def resumo(self, limite=240) -> str:
        texto = " · ".join(parte for parte in self.historico if parte)
        return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _quantidades(itens):
    contagem = Counter()
    for descricao, *_resto, quantidade, _valor in itens:
        contagem[descricao or "item sem nome"] += quantidade
    return contagem


def diferenca_dos_itens(antes, depois, maximo=2) -> str:
    """"+ Air Game Kids ×2, − Pula-pula" -- o que entrou e saiu, curto."""
    a, d = _quantidades(antes), _quantidades(depois)
    partes = []
    for nome in d:
        if d[nome] > a.get(nome, 0):
            mais = d[nome] - a.get(nome, 0)
            partes.append(f"+ {nome}" + (f" ×{mais}" if mais > 1 else ""))
    for nome in a:
        if a[nome] > d.get(nome, 0):
            menos = a[nome] - d.get(nome, 0)
            partes.append(f"− {nome}" + (f" ×{menos}" if menos > 1 else ""))
    if not partes and antes != depois:
        return "valores dos itens"
    if len(partes) > maximo:
        partes = partes[:maximo] + [f"e mais {len(partes) - maximo}"]
    return ", ".join(partes)


def _acertar_pagamento(orcamento, total_antes, resultado):
    """O recebido é o mesmo; o que muda é quanto ele cobre do total novo.

    Pagamento parcial com o total que subiu continua parcial (falta mais);
    o pago que deixou de cobrir volta a parcial e a venda do 100% SAI (ela
    é o retrato do pagamento completo -- nunca fica uma venda de um total
    que não existe mais); o parcial que passou a cobrir vira pago e ganha a
    venda. Tudo por `registrar_pagamento`, a mesma porta do quadro.
    """
    P = Orcamento.StatusPagamento
    if orcamento.status != Orcamento.Status.APROVADO:
        return
    recebido = orcamento.valor_pago or Decimal("0.00")
    if recebido <= 0 and orcamento.status_pagamento not in (P.PARCIAL, P.PAGO):
        return
    if orcamento.total == total_antes:
        return
    situacao_antes = orcamento.status_pagamento
    mudanca = orcamento.registrar_pagamento(recebido, orcamento.observacao_pagamento)
    resultado.venda = mudanca
    falta = orcamento.saldo_pagamento
    if orcamento.status_pagamento == P.PAGO:
        if mudanca.acao == "criada":
            linha = (
                f"Pagamento: os {_moeda(recebido)} recebidos cobrem o total novo "
                f"({_moeda(orcamento.total)}) — ficou pago e virou a venda #{mudanca.venda_id}."
            )
            resultado.historico.append(f"pago · venda #{mudanca.venda_id}")
        else:
            linha = f"Pagamento: continua pago ({_moeda(recebido)} recebidos de {_moeda(orcamento.total)})."
            resultado.historico.append("pagamento continua pago")
    else:
        linha = (
            f"Pagamento: {_moeda(recebido)} recebidos de {_moeda(orcamento.total)} — "
            f"faltam {_moeda(falta)}."
        )
        if situacao_antes == P.PAGO:
            linha = (
                f"Pagamento: o total subiu para {_moeda(orcamento.total)} e o recebido "
                f"({_moeda(recebido)}) não cobre mais — voltou a parcial, faltam {_moeda(falta)}."
            )
        if mudanca.acao == "desfeita":
            linha += f" A venda #{mudanca.venda_id} saiu e volta sozinha quando o pagamento fechar 100%."
            resultado.historico.append(f"pagamento parcial · a venda #{mudanca.venda_id} saiu")
        else:
            resultado.historico.append(f"pagamento parcial (faltam {_moeda(falta)})")
    resultado.lista.append(linha)


def _acertar_montagem(orcamento, resultado):
    """A lista de montagem acompanha os itens (só o que mudou de verdade)."""
    from . import montagem

    try:
        with transaction.atomic():
            mudanca = montagem.acompanhar_itens_do_orcamento(orcamento)
    except Exception:  # noqa: BLE001 -- a proposta nunca cai por causa da lista
        logger.exception("lista de montagem do orçamento %s depois da edição", orcamento.pk)
        resultado.lista.append(
            "Lista de montagem: não deu para acertar agora; ela se acerta sozinha ao abrir."
        )
        return
    resultado.montagem = mudanca
    if not mudanca:
        return
    partes = []
    if mudanca.get("entraram"):
        n = mudanca["entraram"]
        partes.append(f"{n} {'máquina entrou' if n == 1 else 'máquinas entraram'}")
    if mudanca.get("sairam"):
        n = mudanca["sairam"]
        partes.append(f"{n} {'saiu' if n == 1 else 'saíram'}")
    if partes:
        linha = "Lista de montagem: " + " e ".join(partes) + "."
        comecadas = mudanca.get("comecadas_que_sairam", 0)
        if comecadas:
            linha += (
                f" Atenção: {comecadas} já {'estava' if comecadas == 1 else 'estavam'} em "
                "produção ou pronta — avise a Produção."
            )
        resultado.lista.append(linha)
        resultado.historico.append("lista de montagem " + " e ".join(partes))


def _acertar_contrato(orcamento, usuario, resultado):
    """O contrato que espera assinatura é REFEITO com o pedido de agora.

    `documento_assinatura.gerar` (o "Gerar de novo" do cartão): o anterior
    vira substituído e TODOS os links dele morrem na hora; a página do
    cliente diz "Este link foi trocado". Na proposta que deixou de estar
    aprovada (em negociação, com o contrato suspenso), não há compra para
    um contrato novo: o suspenso é RETIRADO, para nunca voltar a valer com
    os itens velhos quando ela for aprovada de novo.
    """
    from . import documento_assinatura as svc

    documento = svc.documento_atual(orcamento)
    if documento is None or documento.assinado:
        return
    links = documento.links_gerados
    aberto = svc.aberto_agora(documento)
    if orcamento.status != Orcamento.Status.APROVADO:
        svc.aposentar(orcamento, usuario, motivo="a proposta mudou depois de o contrato sair")
        resultado.contrato_retirado = True
        resultado.lista.append(
            "O contrato que tinha saído (suspenso) foi retirado: quando o cliente "
            "aprovar de novo, gere o contrato com o pedido de agora."
        )
        resultado.historico.append("contrato suspenso retirado")
        return
    try:
        novo = svc.gerar(orcamento, usuario, motivo="o pedido mudou (itens, valores ou condições)")
    except Exception as erro:  # noqa: BLE001 -- ErroDeFormulario ou o que for: o pedido fica gravado
        logger.warning("contrato do orçamento %s não foi refeito: %s", orcamento.pk, erro)
        svc.aposentar(orcamento, usuario, motivo="a proposta mudou e o contrato não pôde ser refeito")
        resultado.contrato_retirado = True
        resultado.janela_titulo = "Contrato retirado"
        resultado.janela_nivel = "alerta"
        resultado.janela_texto = (
            f"O pedido foi salvo, mas o contrato não pôde ser refeito agora ({erro}). "
            "O anterior foi retirado — os links dele não valem mais. Gere o contrato "
            "de novo pelo cartão do documento."
        )
        resultado.acao = {"rotulo": "Ver contrato", "url": _url("documento_assinatura_inner", orcamento.pk)}
        resultado.historico.append("contrato retirado")
        return
    resultado.contrato_refeito = True
    resultado.documento_novo = novo.pk
    resultado.janela_titulo = "Contrato refeito"
    resultado.janela_nivel = "info"
    resultado.janela_texto = TEXTO_CONTRATO_REFEITO + (
        " O cliente estava com o contrato aberto: peça para ele abrir o link novo."
        if aberto else ""
    )
    resultado.acao = {"rotulo": "Ver contrato", "url": _url("documento_assinatura_inner", orcamento.pk)}
    resultado.historico.append(
        f"contrato refeito (o anterior tinha {links} link{'s' if links != 1 else ''})"
    )


def acompanhar(orcamento, usuario, antes: Antes, itens_depois) -> Resultado:
    """Depois de gravar a proposta: o que deriva dela anda junto.

    Na ordem que importa: o pagamento (o total novo), a lista de montagem
    (ela escreve o prazo que a Cláusula 3ª lê) e por último o contrato
    (que congela tudo isso num retrato novo). Cada um só é tocado quando
    o que ele lê mudou: salvar sem mudar nada não custa consulta a mais.
    """
    resultado = Resultado()
    itens_depois = list(itens_depois)
    linhas_depois = linhas_dos_itens(itens_depois)
    itens_mudaram = linhas_depois != antes.itens
    contrato_mudou = assinatura_do_contrato(orcamento, itens_depois) != antes.contrato

    if itens_mudaram:
        diferenca = diferenca_dos_itens(antes.itens, linhas_depois)
        resultado.historico.append(f"itens: {diferenca}" if diferenca else "itens")
    if orcamento.total != antes.total:
        resultado.historico.append(f"total {_moeda(antes.total)} → {_moeda(orcamento.total)}")

    _acertar_pagamento(orcamento, antes.total, resultado)
    if itens_mudaram and orcamento.status == Orcamento.Status.APROVADO:
        _acertar_montagem(orcamento, resultado)
    if contrato_mudou:
        _acertar_contrato(orcamento, usuario, resultado)

    # A PROPOSTA QUE O CLIENTE JÁ RECEBEU. O link dele mostra a versão de
    # agora: a janela diz isso e oferece o reenvio (o fluxo de sempre).
    if (
        antes.enviada and contrato_mudou
        and orcamento.status in (Orcamento.Status.AGUARDANDO_RESPOSTA, Orcamento.Status.EM_NEGOCIACAO)
    ):
        resultado.historico.append("já enviada ao cliente: o link dele mostra a versão nova")
        if not resultado.janela_titulo:
            resultado.janela_titulo = "Proposta atualizada"
            resultado.janela_nivel = "info"
            resultado.janela_icone = "email"
            resultado.janela_texto = (
                "O cliente já tinha recebido esta proposta. O link dele já mostra o "
                "que mudou — avise o cliente ou mande de novo."
            )
            if orcamento.pode_enviar:
                resultado.acao = {"rotulo": "Reenviar ao cliente", "chave": "reenviar", "id": orcamento.pk}
    elif antes.status == Orcamento.Status.APROVADO and contrato_mudou:
        resultado.historico.append("proposta já aprovada, alterada antes da assinatura")
    return resultado
