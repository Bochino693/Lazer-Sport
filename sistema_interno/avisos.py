"""O que precisa de atenção agora, em um lugar só.

O painel é usado o dia inteiro, quase sempre num tablet apoiado na
bancada. Quem está nele não vai abrir seis telas para descobrir que um
orçamento vence amanhã — o painel é que tem de avisar.

Este módulo é a ÚNICA fonte desses avisos. Antes as contagens viviam
espalhadas: o context_processor contava vendas, pedidos e manutenções com
uma regra, a home recontava estoque crítico com outra, e a tela de
orçamentos tinha a terceira. Três lugares para mudar quando "pendente"
mudasse de significado, e nenhum deles concordando com os outros.

CUSTO. Roda em toda página do painel, então tudo aqui é COUNT agregado —
nada de trazer linha para contar em Python. O estoque crítico era o pior
caso: `situacao` é propriedade do modelo, e a home carregava a tabela
inteira para filtrar na memória. A mesma regra escrita como
`quantidade <= estoque_minimo` vira uma consulta que o banco resolve.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from core.models import Manutencao, Pedido, Venda

from .models import EstoqueMaterial, Orcamento, OrdemProducao
from .permissoes import GESTAO, capacidades, limitar_orcamentos, tem_funcao

#: Rotas do painel. Passado na mão porque um pedido que chegue por fora
#: do subdomínio interno resolveria contra o urlconf do site, onde estes
#: nomes não existem.
URLCONF = "sistema_interno.urls"

#: A partir de quantos dias de validade restantes um orçamento vira
#: cobrança. Três dias é o que dá para ligar para o cliente antes de a
#: proposta morrer sozinha.
DIAS_PARA_COBRAR = 3

#: Janela do que conta como "acabou de acontecer" nas respostas de
#: cliente. Uma semana cobre quem passou o fim de semana fora.
DIAS_DE_NOVIDADE = 7


@dataclass(frozen=True)
class Aviso:
    """Uma linha da central.

    `nivel` decide a cor e a ordem: critico vem antes de atencao, que vem
    antes de novidade, que vem antes de info. É o único critério de
    ordenação — quem lê de relance precisa achar o pior no topo.
    """

    chave: str
    titulo: str
    detalhe: str
    quantidade: int
    url: str
    nivel: str
    icone: str

    @property
    def urgente(self):
        return self.nivel in ("critico", "atencao")


#: Peso de cada nível na ordenação. Fora do dataclass porque é regra de
#: apresentação, não dado do aviso.
PESO = {"critico": 0, "atencao": 1, "novidade": 2, "info": 3}


def eh_gestor(user):
    """Compatibilidade para chamadas antigas da regra de Gestão."""
    return tem_funcao(user, GESTAO)


def _orcamentos(user, hoje):
    """Vencidos e a vencer. Duas consultas, dois avisos diferentes.

    Vencido é perda: a proposta morreu sem resposta. A vencer ainda dá
    para salvar com um telefonema. Juntar os dois num número só apagaria
    justamente a diferença que faz alguém agir.
    """
    abertos = limitar_orcamentos(
        user,
        Orcamento.objects.filter(status__in=Orcamento.EM_ABERTO),
    )

    vencidos = abertos.filter(validade__lt=hoje).count()
    a_vencer = abertos.filter(
        validade__gte=hoje,
        validade__lte=hoje + timedelta(days=DIAS_PARA_COBRAR),
    ).count()

    avisos = []

    if vencidos:
        avisos.append(Aviso(
            chave="orcamentos_vencidos",
            titulo="Orçamento vencido" if vencidos == 1 else "Orçamentos vencidos",
            detalhe="Passou da validade sem resposta do cliente.",
            quantidade=vencidos,
            url=reverse("orcamentos_inner", urlconf=URLCONF),
            nivel="critico",
            icone="bi-calendar-x",
        ))

    if a_vencer:
        avisos.append(Aviso(
            chave="orcamentos_vencendo",
            titulo="Orçamento a vencer" if a_vencer == 1 else "Orçamentos a vencer",
            detalhe=f"Vence em até {DIAS_PARA_COBRAR} dias. Dá tempo de ligar.",
            quantidade=a_vencer,
            url=reverse("orcamentos_inner", urlconf=URLCONF),
            nivel="atencao",
            icone="bi-hourglass-split",
        ))

    return avisos


def _respostas_de_cliente(user, agora):
    """Cliente respondeu pela página pública e ninguém viu ainda.

    É o aviso mais importante da lista em termos de dinheiro: uma proposta
    aprovada que fica parada é uma venda esfriando.
    """
    desde = agora - timedelta(days=DIAS_DE_NOVIDADE)
    respondidos = limitar_orcamentos(
        user,
        Orcamento.objects.filter(respondido_em__gte=desde),
    )

    aprovados = respondidos.filter(status=Orcamento.Status.APROVADO).count()
    recusados = respondidos.filter(status=Orcamento.Status.RECUSADO).count()

    avisos = []

    if aprovados:
        avisos.append(Aviso(
            chave="orcamentos_aprovados",
            titulo="Proposta aprovada" if aprovados == 1 else "Propostas aprovadas",
            detalhe="O cliente aprovou. Combine data e montagem.",
            quantidade=aprovados,
            url=reverse("orcamentos_inner", urlconf=URLCONF) + "?status=aprovado",
            nivel="novidade",
            icone="bi-patch-check",
        ))

    if recusados:
        avisos.append(Aviso(
            chave="orcamentos_recusados",
            titulo="Proposta recusada" if recusados == 1 else "Propostas recusadas",
            detalhe="Vale ler o motivo antes de refazer.",
            quantidade=recusados,
            url=reverse("orcamentos_inner", urlconf=URLCONF) + "?status=recusado",
            nivel="info",
            icone="bi-emoji-frown",
        ))

    return avisos


def _operacao(acesso):
    """Pendências operacionais sem revelar módulos fora da função."""
    avisos = []

    if acesso["pedidos"]:
        pedidos = Pedido.objects.exclude(
            status__in=["finalizado", "cancelado"]
        ).count()
        if pedidos:
            avisos.append(Aviso(
                chave="pedidos",
                titulo="Pedido em aberto" if pedidos == 1 else "Pedidos em aberto",
                detalhe="Ainda não finalizados nem cancelados.",
                quantidade=pedidos,
                url=reverse("pedidos_inner", urlconf=URLCONF),
                nivel="info",
                icone="bi-box2-heart",
            ))

    if acesso["vendas_financeiro"]:
        vendas = Venda.objects.filter(confirmado=False).count()
        if vendas:
            avisos.append(Aviso(
                chave="vendas",
                titulo="Venda a confirmar" if vendas == 1 else "Vendas a confirmar",
                detalhe="Pagamento registrado, confirmação pendente.",
                quantidade=vendas,
                url=reverse("vendas_inner", urlconf=URLCONF),
                nivel="atencao",
                icone="bi-receipt",
            ))

    if acesso["manutencoes"]:
        manutencoes = Manutencao.objects.filter(status__in=["P", "A"]).count()
        if manutencoes:
            avisos.append(Aviso(
                chave="manutencoes",
                titulo="Manutenção aberta" if manutencoes == 1 else "Manutenções abertas",
                detalhe="Chamado do cliente esperando resposta.",
                quantidade=manutencoes,
                url=reverse("manutencao_inner", urlconf=URLCONF),
                nivel="atencao",
                icone="bi-wrench-adjustable",
            ))

    return avisos


def _estoque():
    """Material no mínimo ou abaixo dele.

    A regra mora em `EstoqueMaterialQuerySet.criticos()`, junto do
    modelo, para este módulo e as telas de estoque não terem cada um a
    sua versão do que é "no mínimo".
    """
    criticos = EstoqueMaterial.objects.criticos().count()

    if not criticos:
        return []

    return [Aviso(
        chave="estoque",
        titulo="Material para repor",
        detalhe="No mínimo ou abaixo dele.",
        quantidade=criticos,
        url=reverse("estoque_inner", urlconf=URLCONF),
        nivel="critico",
        icone="bi-box-seam",
    )]


def _producao(user, gestor):
    producoes = OrdemProducao.objects.exclude(
        status__in=[OrdemProducao.Status.CONCLUIDA, OrdemProducao.Status.CANCELADA]
    )

    total = producoes.count()
    if not total:
        return []

    return [Aviso(
        chave="producao",
        titulo="Ordem de produção aberta" if total == 1 else "Ordens de produção abertas",
        detalhe="Na fábrica, ainda não concluídas.",
        quantidade=total,
        url=reverse("minha_producao", urlconf=URLCONF),
        nivel="info",
        icone="bi-hammer",
    )]


def coletar(user):
    """Todos os avisos que este usuário deve ver, do pior para o menor.

    Colaborador que não é gerência não recebe aviso comercial: orçamento,
    venda e faturamento são de gestor, e as próprias telas já recusam a
    entrada. Avisar sobre algo que a pessoa não pode abrir seria só um
    número piscando sem saída.
    """
    if not getattr(user, "is_authenticated", False):
        return []

    acesso = capacidades(user)
    if not any(acesso.values()):
        return []

    hoje = timezone.localdate()
    avisos = []

    if acesso["orcamentos"]:
        avisos += _orcamentos(user, hoje)
        avisos += _respostas_de_cliente(user, timezone.now())

    if acesso["operacao"]:
        avisos += _operacao(acesso)

    if acesso["estoque"]:
        avisos += _estoque()

    if acesso["producao"]:
        # A função é engenharia/acompanhamento de produção, portanto vê a
        # fábrica inteira. A atribuição individual continua destacada nas
        # próprias ordens.
        avisos += _producao(user, True)

    avisos.sort(key=lambda a: (PESO.get(a.nivel, 9), -a.quantidade))
    return avisos
