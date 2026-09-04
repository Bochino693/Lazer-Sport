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

from django.db import DatabaseError, transaction
from django.db.models import Count, Max
from django.urls import reverse
from django.utils import timezone

from core.models import Manutencao, Pedido

from .completude_clientes import filtro_incompletos
from .models import (
    AtividadeOrcamento,
    Cliente,
    EstadoNotificacao,
    EstoqueMaterial,
    Orcamento,
    OrdemProducao,
    OrdemServico,
)
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

# A mesma tabela que memoriza observadores de e-mail guarda até qual evento
# comercial cada usuário já abriu no sino. É estado de notificação, não uma
# segunda cópia do orçamento.
CHAVE_ATIVIDADE_LIDA = "orcamentos_atividade_lida"

# ----------------------------------------------------------------------
# A MEMÓRIA DO SINO É DA CONTA, NÃO DA ABA
#
# O sino balançava quando um aviso crescia com o painel ABERTO. Quem
# fechava o sistema com dez pendências e voltava no dia seguinte com onze
# não via nada: a aba nova começava do zero, guardava "onze" como se
# sempre tivesse sido onze, e a décima primeira movimentação -- justamente
# a que aconteceu enquanto a pessoa não estava -- entrava calada.
#
# Estas linhas guardam, POR USUÁRIO e no banco, quantos avisos de cada
# tipo o sino já anunciou para ele. Quem volta e encontra um número maior
# do que o que lhe foi mostrado recebe a animação na hora, em qualquer
# aparelho, mesmo depois de trocar de navegador.
#
# Aproveita a tabela que já existe (usuário + chave -> quantidade), uma
# linha por tipo de aviso. Nada de coluna nova, nada de migração.
# ----------------------------------------------------------------------
PREFIXO_VISTO = "sino_visto:"

#: Teto defensivo. A central tem uma dúzia de linhas; sem o limite, um
#: POST forjado encheria a tabela de estado com chaves inventadas.
MAXIMO_DE_VISTOS = 40


def avisos_ja_vistos(user):
    """Quanto de cada aviso o sino já mostrou a esta pessoa."""
    if not getattr(user, "pk", None):
        return {}
    try:
        linhas = EstadoNotificacao.objects.filter(
            usuario=user,
            chave__startswith=PREFIXO_VISTO,
        ).values_list("chave", "quantidade")
        return {
            chave[len(PREFIXO_VISTO):]: int(quantidade or 0)
            for chave, quantidade in linhas
        }
    except DatabaseError:
        # Implantação entre o reinício e o migrate: sem memória o sino
        # volta ao comportamento antigo, que é calado -- nunca a 502.
        return {}


def guardar_avisos_vistos(user, mapa):
    """Grava o que o painel acabou de mostrar.

    Substitui o conjunto inteiro em vez de só somar: um aviso RESOLVIDO
    tem de sair da memória, senão, quando o mesmo problema voltar a
    aparecer com o número antigo, o sino ficaria mudo achando que já tinha
    avisado.
    """
    if not getattr(user, "pk", None):
        return {}

    limpo = {}
    for chave, quantidade in list(mapa.items())[:MAXIMO_DE_VISTOS]:
        chave = str(chave or "").strip()[: 80 - len(PREFIXO_VISTO)]
        if not chave:
            continue
        try:
            numero = max(0, int(quantidade))
        except (TypeError, ValueError):
            continue
        # Ausente e zero são a mesma coisa; guardar zero seria uma linha
        # por aviso que a pessoa nem tem.
        if numero:
            limpo[chave] = numero

    try:
        with transaction.atomic():
            EstadoNotificacao.objects.filter(
                usuario=user,
                chave__startswith=PREFIXO_VISTO,
            ).exclude(
                chave__in=[PREFIXO_VISTO + chave for chave in limpo]
            ).delete()
            for chave, numero in limpo.items():
                EstadoNotificacao.objects.update_or_create(
                    usuario=user,
                    chave=PREFIXO_VISTO + chave,
                    defaults={"quantidade": numero},
                )
    except DatabaseError:
        return {}
    return limpo


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
    # Identidades das NEGOCIAÇÕES cobertas pelo aviso. Cada número é a
    # primeira versão da cadeia, portanto v1, v2 e v3 compartilham a mesma
    # referência. Vazio nos avisos que não pertencem a Orçamentos.
    orcamentos: frozenset = frozenset()

    @property
    def urgente(self):
        return self.nivel in ("critico", "atencao")


#: Peso de cada nível na ordenação. Fora do dataclass porque é regra de
#: apresentação, não dado do aviso.
PESO = {"critico": 0, "atencao": 1, "novidade": 2, "info": 3}


def eh_gestor(user):
    """Compatibilidade para chamadas antigas da regra de Gestão."""
    return tem_funcao(user, GESTAO)


def _grupos_de_versoes(orcamento_ids):
    """Transforma ids de versões em ids de negociações distintas.

    Não se pode usar apenas ``distinct(orcamento_id)`` nas atividades:
    refazer cria outro orçamento no banco. O elo ``orcamento_anterior``
    diz que os dois registros são versões do mesmo documento. A busca dos
    pais é feita em lotes por nível, evitando uma consulta para cada evento.
    """
    originais = {int(pk) for pk in orcamento_ids if pk}
    if not originais:
        return frozenset()

    pais = {}
    fronteira = set(originais)
    # Cinquenta também é o limite defensivo usado por cadeia_de_versoes.
    for _ in range(50):
        if not fronteira:
            break
        pares = Orcamento.objects.filter(pk__in=fronteira).values_list(
            "pk", "orcamento_anterior_id",
        )
        proxima = set()
        for pk, pai in pares:
            pais[pk] = pai
            if pai and pai not in pais:
                proxima.add(pai)
        fronteira = proxima

    grupos = set()
    for original in originais:
        atual = original
        vistos = set()
        while pais.get(atual) and atual not in vistos and len(vistos) < 50:
            vistos.add(atual)
            atual = pais[atual]
        grupos.add(atual)
    return frozenset(grupos)


def _orcamentos(user, hoje):
    """Pendências comerciais, vencidas e a vencer.

    A bolinha de Orçamentos representa a fila inteira ainda não finalizada:
    rascunho, aguardando resposta e negociação. Validade decide a urgência,
    não se a proposta existe na fila. Por isso uma proposta válida por mais
    de três dias também precisa entrar no número do menu.

    Vencido é perda; a vencer ainda dá para salvar com um telefonema. Esses
    dois motivos continuam separados na central, mas a mesma negociação
    ocupa uma única unidade no total, inclusive quando já foi refeita.
    """
    abertos = limitar_orcamentos(
        user,
        Orcamento.objects.filter(status__in=Orcamento.EM_ABERTO),
    )

    em_aberto = _grupos_de_versoes(
        abertos.values_list("pk", flat=True)
    )
    vencidos = _grupos_de_versoes(
        abertos.filter(validade__lt=hoje).values_list("pk", flat=True)
    )
    a_vencer = _grupos_de_versoes(abertos.filter(
        validade__gte=hoje,
        validade__lte=hoje + timedelta(days=DIAS_PARA_COBRAR),
    ).values_list("pk", flat=True))

    avisos = []

    if em_aberto:
        quantidade = len(em_aberto)
        avisos.append(Aviso(
            chave="orcamentos_em_aberto",
            titulo=(
                "Proposta em aberto"
                if quantidade == 1 else "Propostas em aberto"
            ),
            detalhe=(
                "Rascunhos, propostas aguardando resposta e negociações "
                "ainda precisam de acompanhamento."
            ),
            quantidade=quantidade,
            url=reverse("orcamentos_inner", urlconf=URLCONF),
            nivel="info",
            icone="bi-file-earmark-text",
            orcamentos=em_aberto,
        ))

    if vencidos:
        quantidade = len(vencidos)
        avisos.append(Aviso(
            chave="orcamentos_vencidos",
            titulo="Orçamento vencido" if quantidade == 1 else "Orçamentos vencidos",
            detalhe="Passou da validade sem resposta do cliente.",
            quantidade=quantidade,
            url=reverse("orcamentos_inner", urlconf=URLCONF),
            nivel="critico",
            icone="bi-calendar-x",
            orcamentos=vencidos,
        ))

    if a_vencer:
        quantidade = len(a_vencer)
        avisos.append(Aviso(
            chave="orcamentos_vencendo",
            titulo="Orçamento a vencer" if quantidade == 1 else "Orçamentos a vencer",
            detalhe=f"Vence em até {DIAS_PARA_COBRAR} dias. Dá tempo de ligar.",
            quantidade=quantidade,
            url=reverse("orcamentos_inner", urlconf=URLCONF),
            nivel="atencao",
            icone="bi-hourglass-split",
            orcamentos=a_vencer,
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

    aprovados = _grupos_de_versoes(
        respondidos.filter(status=Orcamento.Status.APROVADO)
        .values_list("pk", flat=True)
    )
    recusados = _grupos_de_versoes(
        respondidos.filter(status=Orcamento.Status.RECUSADO)
        .values_list("pk", flat=True)
    )

    avisos = []

    if aprovados:
        quantidade = len(aprovados)
        avisos.append(Aviso(
            chave="orcamentos_aprovados",
            titulo="Proposta aprovada" if quantidade == 1 else "Propostas aprovadas",
            detalhe="O cliente aprovou. Combine data e montagem.",
            quantidade=quantidade,
            url=reverse("orcamentos_inner", urlconf=URLCONF) + "?filtro=aprovados",
            nivel="novidade",
            icone="bi-patch-check",
            orcamentos=aprovados,
        ))

    if recusados:
        quantidade = len(recusados)
        avisos.append(Aviso(
            chave="orcamentos_recusados",
            titulo="Proposta recusada" if quantidade == 1 else "Propostas recusadas",
            detalhe="Vale ler o motivo antes de refazer.",
            quantidade=quantidade,
            url=reverse("orcamentos_inner", urlconf=URLCONF) + "?filtro=recusados",
            nivel="info",
            icone="bi-emoji-frown",
            orcamentos=recusados,
        ))

    return avisos


def versao_atividades():
    """Último evento global; uma consulta mínima invalida caches entre workers."""
    try:
        return (
            AtividadeOrcamento.objects.order_by("-id")
            .values_list("id", flat=True)
            .first()
            or 0
        )
    except DatabaseError:
        # Implantação entre o reinício e o migrate: o sino antigo continua
        # funcionando, e uma tabela nova nunca derruba o painel com 502.
        return 0


def versao_ordens_servico():
    """Revisão barata da fila de O.S. para invalidar caches entre usuários.

    O total detecta exclusões; o instante detecta criação e alteração. Isso
    evita criar outra tabela só para o relógio e continua funcionando entre
    os vários workers do Render, porque a fonte é o próprio PostgreSQL.
    """
    try:
        estado = OrdemServico.objects.aggregate(
            total=Count("pk"),
            ultima=Max("atualizado"),
        )
        ultima = estado["ultima"]
        micros = int(ultima.timestamp() * 1_000_000) if ultima else 0
        return f'{estado["total"] or 0}-{micros}'
    except DatabaseError:
        return "0-0"


def _atividades_orcamento(user):
    """O que OUTRA pessoa fez e este usuário ainda não abriu no sino."""
    try:
        estado = EstadoNotificacao.objects.filter(
            usuario=user,
            chave=CHAVE_ATIVIDADE_LIDA,
        ).only("quantidade").first()
        ultimo_lido = estado.quantidade if estado else 0

        # A permissão da lista também limita a notificação. Um vendedor não
        # descobre pelo sino uma proposta que a própria tela esconderia dele.
        visiveis = limitar_orcamentos(
            user,
            Orcamento.objects.all(),
        ).values("pk")
        pendentes = (
            AtividadeOrcamento.objects
            .filter(pk__gt=ultimo_lido, orcamento_id__in=visiveis)
            .exclude(autor=user)
        )
        grupos = _grupos_de_versoes(
            pendentes.values_list("orcamento_id", flat=True).distinct()
        )
        total = len(grupos)
    except DatabaseError:
        return []
    if not total:
        return []

    ultima = pendentes.order_by("-id").first()
    acao = {
        AtividadeOrcamento.Tipo.CRIADO: "criou o orçamento",
        AtividadeOrcamento.Tipo.ALTERADO: "alterou o orçamento",
        AtividadeOrcamento.Tipo.SITUACAO: "mudou a situação do orçamento",
        AtividadeOrcamento.Tipo.REFEITO: "criou uma nova versão do orçamento",
        AtividadeOrcamento.Tipo.PAGAMENTO: "atualizou o pagamento do orçamento",
        AtividadeOrcamento.Tipo.AVALIACAO: "avaliou o orçamento",
        AtividadeOrcamento.Tipo.ENVIADO: "preparou o envio do orçamento",
    }.get(ultima.tipo, "alterou o orçamento")
    detalhe = (
        f"{ultima.autor_nome} {acao} "
        f"#{ultima.orcamento_numero} — {ultima.cliente}."
    )
    if ultima.resumo:
        detalhe += f" {ultima.resumo}."
    if total > 1:
        restantes = total - 1
        detalhe += (
            f" Há mais {restantes} "
            f"{'orçamento' if restantes == 1 else 'orçamentos'} "
            "desde sua última leitura."
        )

    return [Aviso(
        chave="orcamentos_atividade",
        titulo=(
            "Nova movimentação em orçamento"
            if total == 1 else "Novas movimentações em orçamentos"
        ),
        detalhe=detalhe,
        quantidade=total,
        url=reverse("orcamentos_inner", urlconf=URLCONF),
        nivel="novidade",
        icone="bi-bell-fill",
        orcamentos=grupos,
    )]


def marcar_atividades_lidas(user, ate=None):
    """Avança a leitura somente até a versão que o navegador já recebeu.

    Uma movimentação pode nascer entre o último pulso e o clique no sino.
    Sem o limite ``ate``, ela seria marcada como lida antes de aparecer.
    """
    try:
        atividades = AtividadeOrcamento.objects.exclude(autor=user)
        if ate is not None:
            atividades = atividades.filter(pk__lte=max(0, int(ate)))
        ultimo = (
            atividades
            .order_by("-id")
            .values_list("id", flat=True)
            .first()
            or 0
        )
        EstadoNotificacao.objects.update_or_create(
            usuario=user,
            chave=CHAVE_ATIVIDADE_LIDA,
            defaults={"quantidade": ultimo},
        )
        return ultimo
    except (DatabaseError, TypeError, ValueError):
        return 0


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
        # A BOLINHA CONTA O QUE A TELA MOSTRA COMO TRABALHO.
        #
        # Ela contava `core.Venda` não confirmada -- linhas que nada no
        # sistema cria mais, e que a tela de Vendas nem lista: o número do
        # menu e o conteúdo da tela nunca falavam da mesma coisa.
        #
        # O que espera alguém hoje é o recebimento sem comprovante: o
        # cliente pagou e não assinou nada. É um clique em "Gerar
        # documento", e é o que a tela mostra no cartão "Sem documento".
        from .vendas import a_documentar

        vendas = a_documentar().count()
        if vendas:
            avisos.append(Aviso(
                chave="vendas",
                titulo=(
                    "Venda sem comprovante" if vendas == 1
                    else "Vendas sem comprovante"
                ),
                detalhe="Dinheiro recebido, documento ainda não emitido.",
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

    if acesso["ordens_servico"]:
        ordens = OrdemServico.objects.filter(
            status__in=OrdemServico.PENDENTES,
            # Se houver dado legado inconsistente, somente a ponta atual da
            # cadeia ocupa a bolinha; v1/v2/v3 nunca viram três serviços.
            ordem_refeita__isnull=True,
        ).count()
        if ordens:
            avisos.append(Aviso(
                chave="ordens_servico",
                titulo=(
                    "O.S. não finalizada"
                    if ordens == 1 else "Ordens de Serviço não finalizadas"
                ),
                detalhe="Rascunho, ciência, execução, agenda ou peça ainda pendente.",
                quantidade=ordens,
                url=reverse("ordens_servico_inner", urlconf=URLCONF),
                nivel="atencao",
                icone="bi-clipboard2-pulse",
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


def _clientes_incompletos():
    """Cadastros que ainda não sustentam orçamento, contato e deslocamento."""
    total = (
        Cliente.objects
        .filter(ativo=True)
        .filter(filtro_incompletos())
        .distinct()
        .count()
    )
    if not total:
        return []
    return [Aviso(
        chave="clientes_incompletos",
        titulo="Cadastro de cliente incompleto" if total == 1 else "Cadastros de clientes incompletos",
        detalhe="Falta contato, CPF/CNPJ ou endereço. Toque para corrigir.",
        quantidade=total,
        url=reverse("clientes_inner", urlconf=URLCONF) + "?incompletos=1",
        nivel="atencao",
        icone="bi-person-exclamation",
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
        avisos += _atividades_orcamento(user)
        avisos += _orcamentos(user, hoje)
        avisos += _respostas_de_cliente(user, timezone.now())

    if acesso["clientes"]:
        avisos += _clientes_incompletos()

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
