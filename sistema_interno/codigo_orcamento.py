"""O código do orçamento: a proposta do telefone acompanhada em Meus pedidos.

O PEDIDO, nas palavras do dono: "quando tiver em meus pedidos, vai ter
código do pedido, para o caso do seguinte: o cliente fez o orçamento
conosco pelo telefone, aí faz o cadastro, mas como saber que aquele
orçamento vai virar um pedido do site? através do código, fazendo assim o
acompanhamento e mudança de fases pela internet sem necessidade de
contato."

COMO FICOU, EM QUATRO PEÇAS (as telas moram em core/views_codigo_orcamento.py):

  1. O CÓDIGO (`Orcamento.codigo`, sorteado em `gerar_codigo_orcamento`):
     "LS-7K3QX9", seis sinais de um alfabeto sem 0/O/1/I/L. Sai na
     proposta, no e-mail e no WhatsApp. `normalizar` aceita o que a pessoa
     digita de verdade: minúsculas, sem o "LS-", com espaço, com traço.

  2. O VÍNCULO (`vincular`). O cliente logado digita o código em Meus
     pedidos e a proposta passa a ser da conta dele -- a corrente inteira
     de versões, de uma vez. O código de uma versão antiga leva à mais nova
     (`versao_mais_nova`). Proposta que já é de OUTRA conta não muda de
     dono por código: só a equipe resolve, e a tela diz isso.

  3. O FREIO (`freio_esgotado` / `contar_erro`). 8 erros por hora, por
     conta e por IP, no cache. O código é curto para poder ser ditado; o
     que o protege de quem chuta é este teto (e o aviso à equipe a cada
     vínculo).

  4. AS FASES (`acompanhamento`). Cada orçamento vinculado vira um cartão
     com a linha do tempo: Proposta -> Aprovação -> Termo assinado ->
     Pagamento -> Produção -> Concluído. Cada fase sai de um FATO do
     orçamento (status, documento assinado, valor pago, aprovação, O.S.
     concluída): nada é marcado à mão para o cliente ver.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from django.core.cache import cache
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from .models import (
    ALFABETO_DO_CODIGO,
    PREFIXO_DO_CODIGO,
    TAMANHO_DO_CODIGO,
    AtividadeOrcamento,
    DocumentoAssinatura,
    OrdemServico,
    Orcamento,
)

log = logging.getLogger(__name__)


# ======================================================================
# 1. O CÓDIGO
# ======================================================================
_SO_LETRAS_E_NUMEROS = re.compile(r"[^0-9A-Z]")


def normalizar(texto) -> str:
    """O que a pessoa digitou, no formato gravado ("LS-7K3QX9"), ou "".

    Aceita " ls-7k3qx9 ", "LS 7K3 QX9", "7K3QX9", "LS7K3QX9": tira
    espaço, traço e ponto, põe em maiúsculas e tira o "LS" da frente
    quando ele sobra. "" quando não é um código possível (tamanho errado
    ou um sinal fora do alfabeto, como o 0 ou o O) -- esse nem vai ao
    banco, nem conta como tentativa: é erro de digitação, não chute.
    """
    limpo = _SO_LETRAS_E_NUMEROS.sub("", str(texto or "").upper())[:20]
    prefixo = PREFIXO_DO_CODIGO.rstrip("-")
    if len(limpo) == TAMANHO_DO_CODIGO + len(prefixo) and limpo.startswith(prefixo):
        limpo = limpo[len(prefixo):]
    if len(limpo) != TAMANHO_DO_CODIGO or any(c not in ALFABETO_DO_CODIGO for c in limpo):
        return ""
    return PREFIXO_DO_CODIGO + limpo


def versao_mais_nova(orcamento):
    """A última versão da negociação a que este orçamento pertence.

    "Refazer" liga a versão nova à anterior (`orcamento_refeito`). Quem
    recebeu o código da versão 1 e só criou a conta depois da versão 3
    precisa ver a 3 -- é ela que vale. O limite é o mesmo de
    `cadeia_de_versoes`: cinquenta elos é dado corrompido, não negociação.
    """
    atual = orcamento
    for _ in range(50):
        try:
            seguinte = atual.orcamento_refeito
        except Orcamento.DoesNotExist:
            break
        atual = seguinte
    return atual


# ======================================================================
# 2. O VÍNCULO
# ======================================================================
class Vinculo(NamedTuple):
    """O que aconteceu quando a pessoa digitou o código.

    `situacao` é uma de:
      "vinculado"   -- era de ninguém, agora é desta conta;
      "ja_era_seu"  -- já estava nesta conta (nada mudou);
      "outra_conta" -- é de outra conta do site: não muda de dono;
      "inexistente" -- nenhum orçamento com este código;
      "formato"     -- não é um código possível (`normalizar` devolveu "").
    `orcamento` é a versão MAIS NOVA (a que o cartão mostra), quando há.
    `digitado` é o código pedido, já normalizado.
    """

    situacao: str
    orcamento: Orcamento | None = None
    digitado: str = ""

    @property
    def deu_certo(self):
        return self.situacao in ("vinculado", "ja_era_seu")

    @property
    def conta_como_erro(self):
        """O que gasta uma tentativa do freio: o chute que foi ao banco."""
        return self.situacao in ("inexistente", "outra_conta")


def vincular(texto, usuario) -> Vinculo:
    """Liga à conta do site a negociação inteira do código digitado.

    A CORRENTE TODA, E NÃO SÓ A VERSÃO DIGITADA. Assim a pergunta "de quem
    é esta proposta?" tem a mesma resposta em qualquer versão, e a versão 4
    que a equipe criar amanhã já nasce na conta (`Orcamento.save`).

    OUTRA CONTA NÃO PERDE A PROPOSTA POR CÓDIGO. Se qualquer versão já é de
    outra pessoa, nada muda: o código pode ter sido repassado, e quem
    decide é a equipe, que conhece o cliente. As linhas da corrente ficam
    travadas no meio-tempo -- duas contas digitando o mesmo código ao
    mesmo tempo, uma vence e a outra recebe "outra conta".
    """
    codigo = normalizar(texto)
    if not codigo:
        return Vinculo("formato")

    achado = Orcamento.objects.filter(codigo=codigo).first()
    if achado is None:
        return Vinculo("inexistente", digitado=codigo)

    with transaction.atomic():
        mais_nova = versao_mais_nova(achado)
        ids = [versao.pk for versao in mais_nova.cadeia_de_versoes()]
        # Sem select_related: no PostgreSQL o FOR UPDATE não aceita o lado
        # anulável de um LEFT JOIN (ver `documento_assinatura.gerar`).
        cadeia = list(
            Orcamento.objects.select_for_update().filter(pk__in=ids).order_by("pk")
        )
        donos = {versao.conta_id for versao in cadeia if versao.conta_id}
        mais_nova = next(v for v in cadeia if v.pk == mais_nova.pk)
        if donos - {usuario.pk}:
            return Vinculo("outra_conta", mais_nova, codigo)
        if mais_nova.conta_id == usuario.pk and all(v.conta_id for v in cadeia):
            return Vinculo("ja_era_seu", mais_nova, codigo)

        agora = timezone.now()
        primeira_vez = not donos
        sem_dono = [v.pk for v in cadeia if v.conta_id is None]
        # `update`, e não `save`: o vínculo não "edita" a proposta -- a
        # data de atualização dela continua a da última mudança da equipe.
        Orcamento.objects.filter(pk__in=sem_dono).update(
            conta=usuario, vinculado_em=agora,
        )
        mais_nova.refresh_from_db()

    if primeira_vez:
        avisar_a_equipe(mais_nova, usuario, digitado=codigo)
        return Vinculo("vinculado", mais_nova, codigo)
    return Vinculo("ja_era_seu", mais_nova, codigo)


def nome_da_conta(usuario) -> str:
    """"Fulano de Tal (@fulano)", ou só "@fulano" -- como a equipe procura."""
    arroba = f"@{usuario.get_username()}"
    nome = (usuario.get_full_name() or "").strip()
    return f"{nome} ({arroba})" if nome else arroba


def avisar_a_equipe(orcamento, usuario, *, digitado=""):
    """O histórico do orçamento (o sino) e o telefone de quem cuida dele.

    Como no pedido novo do site e na resposta da proposta: a equipe sabe
    na hora que aquele cliente do telefone agora acompanha pelo site --
    e, se não reconhecer a conta, desfaz (`manage.py conta_do_orcamento`)
    antes de qualquer outra fase.
    Nada disto pode estragar o vínculo, que já está gravado: falhou, vai
    para o log.
    """
    versao = "" if digitado in ("", orcamento.codigo) else f" (digitou o da versão anterior, {digitado})"
    try:
        AtividadeOrcamento.objects.create(
            orcamento=orcamento,
            orcamento_numero=orcamento.pk,
            cliente=orcamento.destinatario[:120],
            autor=None,
            autor_nome=f"{nome_da_conta(usuario)} (cliente)"[:150],
            tipo=AtividadeOrcamento.Tipo.VINCULADO,
            resumo=(
                f"Código {orcamento.codigo}{versao} · agora acompanha as fases em Meus pedidos"
            )[:240],
        )
    except Exception:
        log.exception("Não consegui registrar o vínculo do orçamento %s", orcamento.pk)
    try:
        from .notificacoes import avisar_orcamento_vinculado

        avisar_orcamento_vinculado(orcamento)
    except Exception:
        log.exception("Não consegui avisar a equipe do vínculo do orçamento %s", orcamento.pk)


# ======================================================================
# 3. O FREIO
# ======================================================================
#: Erros por janela, por conta e por IP. É o número do pedido de
#: implementação ("ex. 8 tentativas por hora por usuário e por IP").
TENTATIVAS_POR_JANELA = 8
JANELA_DAS_TENTATIVAS = 60 * 60


def _chaves(usuario, ip):
    resumo_ip = hashlib.sha256((ip or "sem-ip").encode()).hexdigest()[:24]
    return (
        f"codigo-orcamento:conta:{getattr(usuario, 'pk', 0)}",
        f"codigo-orcamento:ip:{resumo_ip}",
    )


def freio_esgotado(usuario, ip) -> datetime | None:
    """Quando a pessoa pode tentar de novo -- ou None, se ainda pode agora.

    Só a leitura: o erro é contado à parte (`contar_erro`), depois de o
    código ir ao banco e não servir. Sem cache que funcione, não freia: o
    freio é proteção extra, e quem já tem o código não pode ficar de fora
    porque o cache caiu.
    """
    try:
        for chave in _chaves(usuario, ip):
            if (cache.get(chave) or 0) >= TENTATIVAS_POR_JANELA:
                inicio = cache.get(chave + ":inicio") or time.time()
                return datetime.fromtimestamp(
                    inicio + JANELA_DAS_TENTATIVAS, tz=timezone.get_current_timezone(),
                )
    except Exception:  # noqa: BLE001
        return None
    return None


def contar_erro(usuario, ip):
    """Mais um erro na conta e no IP; a janela começa no primeiro."""
    try:
        for chave in _chaves(usuario, ip):
            if cache.add(chave, 1, JANELA_DAS_TENTATIVAS):
                cache.set(chave + ":inicio", time.time(), JANELA_DAS_TENTATIVAS)
            else:
                cache.incr(chave)
    except Exception:  # noqa: BLE001
        pass


def tentativas_restantes(usuario, ip) -> int:
    try:
        usadas = max((cache.get(chave) or 0) for chave in _chaves(usuario, ip))
    except Exception:  # noqa: BLE001
        usadas = 0
    return max(TENTATIVAS_POR_JANELA - usadas, 0)


# ======================================================================
# 4. AS FASES, COMO O CLIENTE VÊ
# ======================================================================
def orcamentos_da_conta(usuario):
    """Os orçamentos que esta conta acompanha: só a versão mais nova de cada.

    Tudo o que o cartão desenha vem junto, numa conta fixa de consultas
    (itens, documentos de assinatura sem a imagem do traço, a O.S.): a
    página não fica mais lenta com mais orçamentos.
    """
    if not getattr(usuario, "is_authenticated", False):
        return Orcamento.objects.none()
    return (
        Orcamento.objects
        .filter(conta=usuario, orcamento_refeito__isnull=True)
        # a produção (a fila e as etapas, seção 108) vem junto
        .select_related("ordem_servico", "producao")
        .prefetch_related(
            "itens",
            "producao__unidades",
            Prefetch(
                "documentos_assinatura",
                queryset=DocumentoAssinatura.objects
                .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
                # sem a imagem do traço; o retrato fica (a suspensão do
                # termo antigo olha o modelo dele)
                .defer("assinatura_png")
                .order_by("-id"),
                to_attr="documentos_vivos",
            ),
        )
        .order_by("-criacao", "-id")
    )


@dataclass
class Fase:
    """Um passo da linha do tempo do cartão.

    `chave`: proposta, aprovacao, termo, pagamento, producao ou entrega.
    `estado`: "feita" (verde, com o visto), "atual" (acesa, na cor do
    cartão), "parada" (vermelha: recusada, expirada) ou "futura" (apagada).
    `nota` é o fato da fase ("Em 12/11/2026", "Parcial · 40% pago").
    """

    chave: str
    nome: str
    estado: str = "futura"
    nota: str = ""
    #: O desenho é do site: quem mostra o cartão põe o ícone (ver
    #: `core.views_codigo_orcamento.ICONES_DAS_FASES`).
    icone: str = ""


@dataclass
class Acompanhamento:
    """Tudo o que o cartão de um orçamento mostra em Meus pedidos."""

    orcamento: Orcamento
    situacao: str
    situacao_texto: str
    cor: str
    fases: list[Fase] = field(default_factory=list)
    documento: DocumentoAssinatura | None = None
    pode_assinar: bool = False
    termo_assinado: DocumentoAssinatura | None = None
    pode_responder: bool = False
    publicado: bool = False
    mostra_pix: bool = False
    percentual_pago: int = 0
    saldo: Decimal = Decimal("0.00")
    itens: list = field(default_factory=list)
    aviso: str = ""
    #: A conversa com a equipe já escrita (posta pela tela do site).
    whatsapp: str = ""
    #: A fila e as etapas da fábrica (sistema_interno.montagem, seção 108).
    producao: object = None

    @property
    def fase_atual(self):
        return next((f for f in self.fases if f.estado == "atual"), None)


def _dia(momento) -> str:
    if not momento:
        return ""
    if isinstance(momento, datetime):
        momento = timezone.localtime(momento).date()
    return momento.strftime("%d/%m/%Y")


def _documento_vivo(orcamento):
    """O documento que vale (o assinado, ou o que espera assinatura).

    O mesmo critério de `documento_assinatura.documento_atual`, lido da
    lista que `orcamentos_da_conta` já trouxe -- sem uma consulta por
    cartão.
    """
    if hasattr(orcamento, "documentos_vivos"):
        documentos = orcamento.documentos_vivos
    else:
        documentos = list(
            orcamento.documentos_assinatura
            .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
            .defer("assinatura_png").order_by("-id")
        )
    return documentos[0] if documentos else None


def _ordem_servico(orcamento):
    try:
        return orcamento.ordem_servico
    except OrdemServico.DoesNotExist:
        return None


def percentual_pago(orcamento) -> int:
    """Quanto do total já entrou, de 0 a 100 (para a fase do pagamento)."""
    total = orcamento.total
    if orcamento.quitado:
        return 100
    if not total or total <= 0:
        return 0
    return max(0, min(99, int((orcamento.valor_pago or 0) * 100 / total)))


def acompanhamento(orcamento, *, hoje=None) -> Acompanhamento:
    """As fases do orçamento, pelo que de fato aconteceu com ele.

    A ORDEM É A DO PAINEL (LEIA-ME-V10, seção 81): proposta -> aprovação
    -> termo assinado -> pagamento -> produção -> concluído. Cada fase é
    "feita" pelo fato dela; a primeira que falta é a "atual". O pagamento
    pode chegar antes da assinatura (o cliente que paga no balcão existe):
    a fase mostra o que entrou mesmo quando ainda não é a vez dela.
    """
    from . import documento_assinatura as svc_doc

    hoje = hoje or timezone.localdate()
    Status = Orcamento.Status
    status = orcamento.status
    aprovado = status == Status.APROVADO
    vencido = orcamento.vencido or status == Status.EXPIRADO
    documento = _documento_vivo(orcamento) if orcamento.pk else None
    assinado = bool(documento and documento.assinado)
    suspenso = bool(
        documento and not assinado and svc_doc.motivo_da_suspensao(documento, orcamento)
    )
    ordem = _ordem_servico(orcamento)
    # A LISTA DE MONTAGEM (seção 108): a fila, as etapas, o pronto e o
    # entregue da fábrica -- o mesmo fato que a equipe marca no painel.
    from .montagem import _producao_ja_lida, acompanhamento_da_producao

    fabrica = _producao_ja_lida(orcamento) if orcamento.pk else None
    if fabrica is None and orcamento.pk and "producao" not in orcamento._state.fields_cache:
        from .models import ProducaoOrigem

        fabrica = (
            ProducaoOrigem.objects.filter(orcamento=orcamento)
            .exclude(situacao=ProducaoOrigem.Situacao.CANCELADA).first()
        )
    vista = acompanhamento_da_producao(fabrica) if fabrica is not None else None
    entregue_na_lista = bool(fabrica and fabrica.situacao == fabrica.Situacao.ENTREGUE)
    concluido = bool(ordem and ordem.status == OrdemServico.Status.CONCLUIDA) or entregue_na_lista
    pct = percentual_pago(orcamento)

    proposta = Fase("proposta", "Proposta")
    aprovacao = Fase("aprovacao", "Aprovação")
    termo = Fase("termo", "Termo assinado")
    pagamento = Fase("pagamento", "Pagamento")
    producao = Fase("producao", "Produção")
    # "Entregue", o mesmo nome da última fase do pedido do site: os dois
    # funis terminam igual (seção 108)
    entrega = Fase("entrega", "Entregue")
    fases = [proposta, aprovacao, termo, pagamento, producao, entrega]

    # 1. A PROPOSTA
    if status == Status.RASCUNHO:
        proposta.nota = "A equipe está montando"
    else:
        proposta.estado = "feita"
        proposta.nota = f"Enviada em {_dia(orcamento.enviado_em)}" if orcamento.enviado_em else "Enviada"

    # 2. A APROVAÇÃO
    if aprovado:
        aprovacao.estado = "feita"
        quando = orcamento.respondido_em or orcamento.producao_inicio
        aprovacao.nota = f"Em {_dia(quando)}" if quando else "Aprovada"
    elif status == Status.RECUSADO:
        aprovacao.estado = "parada"
        aprovacao.nota = (
            f"Recusada em {_dia(orcamento.respondido_em)}" if orcamento.respondido_em else "Recusada"
        )
    elif status == Status.SUBSTITUIDO:
        aprovacao.estado = "parada"
        aprovacao.nota = "Trocada por outra versão"
    elif vencido:
        aprovacao.estado = "parada"
        aprovacao.nota = (
            f"Validade encerrada em {_dia(orcamento.validade)}" if orcamento.validade
            else "Validade encerrada"
        )
    elif status == Status.EM_NEGOCIACAO:
        aprovacao.nota = "Você pediu ajustes: a nova versão vem aqui"
    elif status == Status.AGUARDANDO_RESPOSTA:
        aprovacao.nota = (
            f"Esperando sua resposta até {_dia(orcamento.validade)}" if orcamento.validade
            else "Esperando sua resposta"
        )

    # 3. O TERMO DE COMPRA
    if assinado:
        termo.estado = "feita"
        termo.nota = f"Em {_dia(documento.assinado_em)}"
    elif aprovado:
        if documento is None:
            termo.nota = "A equipe está preparando o termo"
        elif suspenso:
            termo.nota = "Suspenso: fale com a equipe"
        else:
            termo.nota = "Pronto para você assinar"

    # 4. O PAGAMENTO
    if orcamento.quitado:
        pagamento.estado = "feita"
        pagamento.nota = f"Pago em {_dia(orcamento.pago_em)}" if orcamento.pago_em else "Pago"
    elif aprovado:
        if orcamento.status_pagamento == Orcamento.StatusPagamento.PARCIAL:
            pagamento.nota = f"Parcial · {pct}% pago"
        elif orcamento.status_pagamento == Orcamento.StatusPagamento.ESTORNADO:
            pagamento.nota = "Estornado"
        else:
            pagamento.nota = "Pendente"

    # 5. A PRODUÇÃO
    if orcamento.prazo_producao_dias == 0:
        producao.nota = "Pronta entrega"
    elif aprovado and orcamento.inicio_da_producao:
        previsao = orcamento.previsao_producao
        producao.nota = f"Começou em {_dia(orcamento.inicio_da_producao)}"
        if previsao:
            producao.nota += f" · previsão {_dia(previsao)}"
    elif orcamento.prazo_producao_dias:
        producao.nota = orcamento.prazo_para_o_cliente
    elif aprovado:
        producao.nota = "A equipe informa o prazo"
    if vista is not None:
        producao.nota = vista.nota
        if vista.pronta:
            producao.estado = "feita"

    # 6. CONCLUÍDO (a O.S. da entrega/instalação, ou a entrega marcada na
    # lista de montagem)
    if concluido:
        producao.estado = "feita"
        entrega.estado = "feita"
        quando = ordem.concluida_em if (ordem and ordem.status == OrdemServico.Status.CONCLUIDA) else None
        quando = quando or (fabrica.entregue_em if entregue_na_lista else None)
        entrega.nota = f"Entregue em {_dia(quando)}" if quando else "Entregue"
    elif vista is not None and vista.pronta:
        entrega.nota = "Pronta: a equipe combina a entrega"
    elif ordem and ordem.agendada_para and ordem.status != OrdemServico.Status.CANCELADA:
        entrega.nota = f"Agendado para {_dia(ordem.agendada_para)}"
    elif aprovado:
        entrega.nota = orcamento.forma_envio or "Retirada ou envio a combinar"

    # A fase de agora: a primeira que falta -- se a corrente não parou.
    parou = any(f.estado == "parada" for f in fases)
    if not parou:
        for fase in fases:
            if fase.estado != "feita":
                fase.estado = "atual"
                break

    # A SITUAÇÃO, NUMA FRASE E NUMA COR (o chip do cartão).
    if status == Status.RASCUNHO:
        situacao, texto, cor = "preparando", "Em preparação", "azul"
    elif status == Status.RECUSADO:
        situacao, texto, cor = "recusado", "Recusado", "vermelho"
    elif status == Status.SUBSTITUIDO:
        situacao, texto, cor = "substituido", "Substituído", "roxo"
    elif vencido:
        situacao, texto, cor = "expirado", "Validade encerrada", "vermelho"
    elif status == Status.EM_NEGOCIACAO:
        situacao, texto, cor = "ajustes", "Ajustes pedidos", "roxo"
    elif status == Status.AGUARDANDO_RESPOSTA:
        situacao, texto, cor = "resposta", "Esperando sua resposta", "amarelo"
    elif concluido:
        situacao, texto, cor = "concluido", "Entregue", "verde"
    elif not assinado and documento is not None and not suspenso:
        situacao, texto, cor = "assinar", "Falta assinar o termo", "amarelo"
    elif vista is not None and vista.pronta:
        situacao, texto, cor = "producao", "Pronta para a entrega", "verde"
    elif orcamento.quitado:
        situacao, texto, cor = "producao", "Pago · em produção", "verde"
    elif orcamento.status_pagamento == Orcamento.StatusPagamento.PARCIAL:
        situacao, texto, cor = "pagamento", f"Pagamento parcial · {pct}%", "ciano"
    else:
        situacao, texto, cor = "aprovado", "Aprovado · pagamento pendente", "ciano"

    aviso = ""
    if status == Status.RECUSADO:
        aviso = "Você recusou esta proposta. Se mudou de ideia, a equipe prepara uma nova versão."
    elif status == Status.SUBSTITUIDO:
        aviso = "Esta versão foi trocada por outra. Fale com a equipe se ela não aparecer aqui."
    elif vencido:
        aviso = "O prazo desta proposta acabou. Peça uma nova versão com o preço de hoje."

    publicado = orcamento.publicado
    return Acompanhamento(
        orcamento=orcamento,
        situacao=situacao,
        situacao_texto=texto,
        cor=cor,
        fases=fases,
        documento=documento,
        pode_assinar=bool(aprovado and documento and documento.aguardando and not suspenso),
        termo_assinado=documento if assinado else None,
        pode_responder=(
            status == Status.AGUARDANDO_RESPOSTA and not orcamento.vencido
        ),
        publicado=publicado,
        mostra_pix=bool(aprovado and not orcamento.quitado),
        percentual_pago=pct,
        saldo=orcamento.saldo_pagamento,
        # Rascunho não mostra item nem valor: enquanto a equipe monta a
        # proposta, nem o link dela abre (ver `OrcamentoPublicoView`).
        itens=list(orcamento.itens.all()) if publicado else [],
        aviso=aviso,
        producao=vista,
    )


def orcamento_da_conta(codigo, usuario):
    """O orçamento deste código, SE for desta conta -- senão None.

    É a porta das ações do cartão (assinar o termo): o código vem do
    formulário, e a conta tem de ser a de quem está logado. A versão é a
    mais nova: o cartão nunca mostra outra.
    """
    codigo = normalizar(codigo)
    if not codigo or not getattr(usuario, "is_authenticated", False):
        return None
    orcamento = Orcamento.objects.filter(codigo=codigo, conta=usuario).first()
    if orcamento is None:
        return None
    mais_nova = versao_mais_nova(orcamento)
    return mais_nova if mais_nova.conta_id == usuario.pk else None
