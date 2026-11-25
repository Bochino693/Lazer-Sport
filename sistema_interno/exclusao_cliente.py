"""APAGAR O CLIENTE COM TUDO O QUE É DELE (LEIA-ME-V10, seção 141).

O pedido do dono: o cadastro de um cliente "deve ser apagado inclusive, com
seus pedidos e também os outros objetos associados, para padronizar e
passar a informação coerente".

A exclusão de cliente que já existia (`views_clientes.acao_delete`) apaga
só o cadastro: os orçamentos e as O.S. ficam "sem cliente vinculado"
(SET_NULL). Para um cadastro de teste ou errado isso deixa a casa cheia de
propostas, contratos e vendas de ninguém. Aqui mora a OUTRA exclusão, que
só o superusuário pede: o cliente e tudo o que só existe por causa dele.

O QUE É "DO CLIENTE" (vai junto), levantado das relações dos models:

  * os ORÇAMENTOS ligados a ele, em todas as versões (a corrente
    `orcamento_anterior`, para trás e para a frente), cada um com os
    itens, os envios, a revisão dos blocos e o histórico de atividades;
  * o ACEITE eletrônico e os DOCUMENTOS DE ASSINATURA desses orçamentos
    (contrato, termo ou ordem de serviço, assinados ou não) -- eles
    protegem o orçamento (PROTECT) e saem antes;
  * a VENDA que nasceu do pagamento 100% de um desses orçamentos
    (`Orcamento.delete` já a leva; aqui ela é contada e vai para o rastro);
  * a PRODUÇÃO desses orçamentos na lista de montagem (`ProducaoOrigem` e
    as unidades dela);
  * as ORDENS DE SERVIÇO ligadas a ele ou nascidas desses orçamentos, em
    todas as versões, com os itens, os envios, os documentos anexados e os
    documentos de assinatura;
  * os ENDEREÇOS do cadastro.

O QUE NÃO É SÓ DELE (fica, e a folha avisa):

  * as MOVIMENTAÇÕES DE ESTOQUE em que ele é o destinatário: o material
    saiu de verdade, e apagar a linha deixaria a contagem do estoque sem
    explicação. A linha fica, sem o destinatário, com o nome dele anotado;
  * os OUTROS CLIENTES que ele atende como buffet: ficam, sem o buffet;
  * as ENTREGAS DE CAMPANHA (o que já foi enviado) e os descadastros de
    e-mail: são o registro da campanha, e o descadastro precisa continuar
    valendo;
  * a CONTA DO SITE que acompanha um desses orçamentos, os PEDIDOS DA LOJA
    feitos por ela e os pedidos de MANUTENÇÃO do site: são da conta, e não
    do cadastro do painel. Apagam-se em "Contas de clientes";
  * produtos, peças, materiais e tudo o que é catálogo.

Tudo acontece numa transação: ou sai tudo, ou não sai nada. E fica o
rastro (`ExclusaoRegistrada`) com o que foi junto, número por número.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import ProtectedError, Q

from .models import (
    AceiteOrcamento,
    AtividadeOrcamento,
    Cliente,
    DocumentoAssinatura,
    EntregaCampanha,
    ExclusaoRegistrada,
    MovimentoEstoque,
    Orcamento,
    OrdemServico,
    ProducaoOrigem,
)
from .utils import ErroDeFormulario

ASSINADO = DocumentoAssinatura.Situacao.ASSINADO


def _fechar_corrente(modelo, campo_anterior, ids) -> set:
    """Todas as versões: quem veio antes e quem veio depois de cada uma."""
    todos = set(ids)
    fronteira = set(ids)
    while fronteira:
        vizinhos = set(
            modelo.objects.filter(**{f"{campo_anterior}__in": fronteira}).values_list("pk", flat=True)
        ) | set(
            modelo.objects.filter(pk__in=fronteira)
            .exclude(**{f"{campo_anterior}__isnull": True})
            .values_list(campo_anterior, flat=True)
        )
        fronteira = vizinhos - todos
        todos |= fronteira
    return todos


@dataclass
class Levantamento:
    """O que vai junto e o que fica, contado antes de qualquer coisa sair."""

    cliente: Cliente
    orcamentos: list = field(default_factory=list)  # ids
    ordens: list = field(default_factory=list)  # ids
    documentos: int = 0
    documentos_assinados: int = 0
    aceites: int = 0
    vendas: list = field(default_factory=list)  # ids
    producoes: int = 0
    atividades: int = 0
    enderecos: int = 0
    # o que fica
    movimentos_estoque: int = 0
    clientes_atendidos: int = 0
    entregas_campanha: int = 0
    contas_do_site: int = 0
    pagos: int = 0  # orçamentos e O.S. com dinheiro recebido

    @property
    def vai_junto(self) -> list[dict]:
        """As linhas da folha: só o que existe (zero não aparece)."""
        linhas = [
            ("orcamentos", len(self.orcamentos), "orçamento", "orçamentos", "todas as versões, com itens, envios e histórico"),
            ("ordens", len(self.ordens), "ordem de serviço", "ordens de serviço", "com itens, envios e documentos anexados"),
            ("documentos", self.documentos, "documento de assinatura", "documentos de assinatura",
             (f"{self.documentos_assinados} já assinado{'s' if self.documentos_assinados != 1 else ''} pelo cliente"
              if self.documentos_assinados else "nenhum assinado ainda")),
            ("aceites", self.aceites, "aceite eletrônico", "aceites eletrônicos", "a aprovação registrada na proposta"),
            ("vendas", len(self.vendas), "venda", "vendas", "a receita do pagamento 100% sai do Financeiro"),
            ("producoes", self.producoes, "produção na lista de montagem", "produções na lista de montagem", "com as etapas marcadas"),
            ("enderecos", self.enderecos, "endereço", "endereços", "do cadastro"),
        ]
        return [
            {"chave": chave, "quantos": quantos, "rotulo": singular if quantos == 1 else plural, "nota": nota}
            for chave, quantos, singular, plural, nota in linhas if quantos
        ]

    @property
    def fica(self) -> list[dict]:
        linhas = [
            ("movimentos_estoque", self.movimentos_estoque, "movimentação de estoque", "movimentações de estoque",
             "o material saiu de verdade: a linha fica, sem o destinatário, com o nome dele anotado"),
            ("clientes_atendidos", self.clientes_atendidos, "cliente atendido por ele", "clientes atendidos por ele",
             "o cadastro continua, sem o buffet"),
            ("entregas_campanha", self.entregas_campanha, "envio de campanha", "envios de campanha",
             "o registro do que já foi enviado continua na campanha"),
            ("contas_do_site", self.contas_do_site, "conta do site", "contas do site",
             "a conta e os pedidos da loja dela não são apagados aqui (Contas de clientes)"),
        ]
        return [
            {"chave": chave, "quantos": quantos, "rotulo": singular if quantos == 1 else plural, "nota": nota}
            for chave, quantos, singular, plural, nota in linhas if quantos
        ]

    @property
    def tem_o_que_levar(self) -> bool:
        return bool(self.orcamentos or self.ordens)

    def como_json(self) -> dict:
        return {
            "cliente": self.cliente.nome_cliente,
            "vai_junto": self.vai_junto,
            "fica": self.fica,
            "pagos": self.pagos,
            "assinados": self.documentos_assinados,
            "tem_o_que_levar": self.tem_o_que_levar,
        }


def levantar(cliente) -> Levantamento:
    """Conta o que é do cliente. Só lê."""
    orcamentos = _fechar_corrente(
        Orcamento, "orcamento_anterior",
        Orcamento.objects.filter(cliente=cliente).values_list("pk", flat=True),
    )
    ordens = _fechar_corrente(
        OrdemServico, "ordem_anterior",
        OrdemServico.objects.filter(Q(cliente=cliente) | Q(orcamento__in=orcamentos)).values_list("pk", flat=True),
    )
    documentos = DocumentoAssinatura.objects.filter(Q(orcamento__in=orcamentos) | Q(ordem_servico__in=ordens))
    dos_orcamentos = Orcamento.objects.filter(pk__in=orcamentos)
    return Levantamento(
        cliente=cliente,
        orcamentos=sorted(orcamentos),
        ordens=sorted(ordens),
        documentos=documentos.count(),
        documentos_assinados=documentos.filter(situacao=ASSINADO).count(),
        aceites=AceiteOrcamento.objects.filter(orcamento__in=orcamentos).count(),
        vendas=sorted(dos_orcamentos.exclude(venda__isnull=True).values_list("venda_id", flat=True)),
        producoes=ProducaoOrigem.objects.filter(orcamento__in=orcamentos).count(),
        atividades=AtividadeOrcamento.objects.filter(orcamento__in=orcamentos).count(),
        enderecos=cliente.enderecos.count(),
        movimentos_estoque=MovimentoEstoque.objects.filter(cliente=cliente).count(),
        clientes_atendidos=cliente.clientes_atendidos.count(),
        entregas_campanha=EntregaCampanha.objects.filter(cliente=cliente).count(),
        contas_do_site=dos_orcamentos.exclude(conta__isnull=True).values("conta_id").distinct().count(),
        pagos=(
            dos_orcamentos.filter(valor_pago__gt=0).count()
            + OrdemServico.objects.filter(pk__in=ordens, valor_pago__gt=0).count()
        ),
    )


def _lista(numeros, limite=40) -> str:
    numeros = list(numeros)
    texto = ", ".join(str(n) for n in numeros[:limite])
    return texto + (f" e mais {len(numeros) - limite}" if len(numeros) > limite else "")


def apagar_com_tudo(cliente, *, autor, motivo: str = "") -> Levantamento:
    """Apaga o cliente e tudo o que é dele, e registra. Só o superusuário.

    Quem chama já conferiu a confirmação escrita. A conferência de quem
    pede fica AQUI também: esta função não confia na tela.
    """
    if not getattr(autor, "is_superuser", False):
        raise ErroDeFormulario(
            "Apagar o cliente com os orçamentos e as ordens de serviço é só do superusuário.",
        )

    with transaction.atomic():
        # a linha do cliente travada: ninguém abre um orçamento novo para ele no meio
        cliente = Cliente.objects.select_for_update().get(pk=cliente.pk)
        nome = cliente.nome_cliente
        levantamento = levantar(cliente)
        orcamentos = list(
            Orcamento.objects.filter(pk__in=levantamento.orcamentos).order_by("-pk")
        )
        ordens = list(OrdemServico.objects.filter(pk__in=levantamento.ordens).order_by("-pk"))
        assinados = list(
            DocumentoAssinatura.objects
            .filter(Q(orcamento__in=levantamento.orcamentos) | Q(ordem_servico__in=levantamento.ordens))
            .filter(situacao=ASSINADO)
            .values_list("assinante_nome", "assinado_em")
        )
        numeros_orcamentos = [f"#{o.pk} ({o.get_status_display()}, R$ {o.total})" for o in orcamentos]
        numeros_ordens = [f"{o.numero_documento} ({o.get_status_display()})" for o in ordens]

        try:
            # 1) o que PROTEGE o orçamento e a O.S. sai primeiro
            DocumentoAssinatura.objects.filter(
                Q(orcamento__in=levantamento.orcamentos) | Q(ordem_servico__in=levantamento.ordens)
            ).delete()
            AceiteOrcamento.objects.filter(orcamento__in=levantamento.orcamentos).delete()
            # 2) o histórico da proposta ficaria solto (SET_NULL): vai junto
            AtividadeOrcamento.objects.filter(orcamento__in=levantamento.orcamentos).delete()
            # 3) as O.S. (itens, envios e anexos saem em cascata; o arquivo
            #    do anexo é apagado pelo sinal do modelo)
            for ordem in ordens:
                ordem.delete()
            # 4) os orçamentos, um a um: `Orcamento.delete` leva a venda do
            #    pagamento 100%, e a produção da lista de montagem sai em cascata
            for orcamento in orcamentos:
                orcamento.delete()
            # 5) o estoque NÃO volta: o material saiu. A linha fica, sem o
            #    destinatário (que deixa de existir) e com o nome anotado.
            for movimento in MovimentoEstoque.objects.filter(cliente=cliente):
                anotacao = f"Destinatário removido: {nome}"
                movimento.cliente = None
                movimento.motivo = (
                    f"{movimento.motivo} · {anotacao}" if movimento.motivo else anotacao
                )[:150]
                movimento.save(update_fields=["cliente", "motivo"])
            # 6) o cadastro (os endereços saem em cascata)
            cliente.delete()
        except ProtectedError as erro:
            presos = ", ".join(sorted({type(item).__name__ for item in erro.protected_objects}))
            raise ErroDeFormulario(
                "Não consegui apagar tudo: ainda existe registro protegido "
                f"({presos}). Nada foi apagado."
            ) from erro

        partes = [
            f"Documento: {cliente.documento or '—'}. Telefone: {cliente.telefone or '—'}.",
            "APAGADO COM TUDO O QUE ERA DELE.",
        ]
        if numeros_orcamentos:
            partes.append(f"Orçamentos ({len(numeros_orcamentos)}): {_lista(numeros_orcamentos)}.")
        if numeros_ordens:
            partes.append(f"Ordens de serviço ({len(numeros_ordens)}): {_lista(numeros_ordens)}.")
        if levantamento.documentos:
            partes.append(
                f"Documentos de assinatura: {levantamento.documentos} "
                f"({levantamento.documentos_assinados} assinado(s))."
            )
        if assinados:
            partes.append(
                "Assinados por: " + _lista(
                    f"{quem} em {quando:%d/%m/%Y}" if quando else quem for quem, quando in assinados
                ) + "."
            )
        if levantamento.aceites:
            partes.append(f"Aceites eletrônicos: {levantamento.aceites}.")
        if levantamento.vendas:
            partes.append(f"Vendas removidas da receita: {_lista('#' + str(v) for v in levantamento.vendas)}.")
        if levantamento.producoes:
            partes.append(f"Produções na lista de montagem: {levantamento.producoes}.")
        if levantamento.atividades:
            partes.append(f"Linhas de histórico das propostas: {levantamento.atividades}.")
        if levantamento.enderecos:
            partes.append(f"Endereços: {levantamento.enderecos}.")
        ficou = [f"{linha['quantos']} {linha['rotulo']}" for linha in levantamento.fica]
        if ficou:
            partes.append("FICOU (não era só dele): " + "; ".join(ficou) + ".")

        ExclusaoRegistrada.objects.create(
            autor=autor if getattr(autor, "pk", None) else None,
            autor_nome=(
                getattr(autor, "get_full_name", lambda: "")() or getattr(autor, "username", "") or "desconhecido"
            ),
            tipo="Cliente (com tudo)",
            identificacao=nome[:200],
            resumo="\n".join(partes),
            motivo=(motivo or "")[:240],
            forcada=True,
        )
    return levantamento
