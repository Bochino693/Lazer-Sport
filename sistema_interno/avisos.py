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

from django.db import DatabaseError, connection, transaction
from django.db.models import Count, Exists, IntegerField, Max, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from core.models import Manutencao, Pedido, Venda

from .completude_clientes import filtro_incompletos, partes_incompletas
from .models import (
    AtividadeOrcamento,
    Cliente,
    DocumentoAssinatura,
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

    # POUCAS IDAS AO BANCO (LEIA-ME-V10, seção 120). Era um
    # `update_or_create` por aviso -- SAVEPOINT, SELECT, UPDATE ou INSERT e
    # RELEASE: quatro viagens ao Supabase cada, ~30 para uma central de oito
    # avisos (~5 s de uma thread do servidor presa, a cada número novo no
    # sino). Agora: as linhas desta pessoa numa leitura (travadas, como o
    # `update_or_create` travava), e as que saem, as que mudam e as que
    # nascem, cada grupo num comando só. O resultado gravado é o mesmo.
    try:
        with transaction.atomic():
            existentes = {
                estado.chave: estado
                for estado in EstadoNotificacao.objects.select_for_update().filter(
                    usuario=user,
                    chave__startswith=PREFIXO_VISTO,
                )
            }
            desejadas = {PREFIXO_VISTO + chave: numero for chave, numero in limpo.items()}
            sobrando = [estado.pk for chave, estado in existentes.items() if chave not in desejadas]
            if sobrando:
                EstadoNotificacao.objects.filter(pk__in=sobrando).delete()
            agora = timezone.now()
            mudaram = []
            for chave, numero in desejadas.items():
                estado = existentes.get(chave)
                if estado is not None and estado.quantidade != numero:
                    estado.quantidade = numero
                    estado.atualizado = agora
                    mudaram.append(estado)
            if mudaram:
                EstadoNotificacao.objects.bulk_update(mudaram, ["quantidade", "atualizado"])
            novas = [
                EstadoNotificacao(usuario=user, chave=chave, quantidade=numero)
                for chave, numero in desejadas.items()
                if chave not in existentes
            ]
            if novas:
                # Outra aba da mesma pessoa pode ter criado a linha agora
                # mesmo: o índice único (usuário, chave) segura, e a
                # repetida simplesmente não entra.
                EstadoNotificacao.objects.bulk_create(novas, ignore_conflicts=True)
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
    # O QUE FAZER, EM DUAS PALAVRAS (LEIA-ME-V10, seção 116): o rótulo do
    # botão que aparece no próprio aviso ("Completar", "Combinar entrega").
    # O detalhe explica; a ação é o que o dedo procura.
    acao: str = ""

    @property
    def urgente(self):
        return self.nivel in ("critico", "atencao")

    @property
    def resolvivel(self):
        """Abre a folha de conserto em vez de levar para outra tela."""
        return self.chave in RESOLVIVEIS


#: Peso de cada nível na ordenação. Fora do dataclass porque é regra de
#: apresentação, não dado do aviso.
PESO = {"critico": 0, "atencao": 1, "novidade": 2, "info": 3}

# ----------------------------------------------------------------------
# OS AVISOS QUE SE RESOLVEM ALI MESMO (LEIA-ME-V10, seção 116)
#
# "Melhore as notificações, deixe modais para solucionar problemas
# pequenos." Cada chave abaixo abre uma folha no próprio sino (e no
# Início) com a lista do que falta e as ações que já existem nas telas.
# O valor é a capacidade de `permissoes.capacidades` que abre a folha --
# a MESMA que decide quem recebe o aviso, para nunca existir aviso com
# folha que a pessoa não abre. As ações de dentro da folha conferem, cada
# uma, a regra da tela de onde vêm (ver `resolver_avisos.py`).
#
# O que fica de fora continua levando para a tela: produção, O.S.,
# manutenção, vendas a confirmar, projetos 3D e as movimentações de
# colegas não têm um conserto de um toque.
# ----------------------------------------------------------------------
RESOLVIVEIS = {
    "clientes_incompletos": "clientes",
    "orcamentos_aprovados": "orcamentos",
    "orcamentos_em_aberto": "orcamentos",
    "orcamentos_vencendo": "orcamentos",
    "orcamentos_vencidos": "orcamentos",
    "orcamentos_recusados": "orcamentos",
    "pedidos": "pedidos",
    "estoque": "estoque",
}


def _plural(numero, um, varios):
    return f"{numero} {um if numero == 1 else varios}"


def _lista_em_frase(partes):
    """["a", "b", "c"] -> "a, b e c"."""
    partes = [p for p in partes if p]
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " e " + partes[-1]


def eh_gestor(user):
    """Compatibilidade para chamadas antigas da regra de Gestão."""
    return tem_funcao(user, GESTAO)


def _grupos_de_versoes(orcamento_ids, negociacao=None):
    """Transforma ids de versões em ids de negociações distintas.

    Não se pode usar apenas ``distinct(orcamento_id)`` nas atividades:
    refazer cria outro orçamento no banco. O elo ``orcamento_anterior``
    diz que os dois registros são versões do mesmo documento. A busca dos
    pais é feita em lotes por nível, evitando uma consulta para cada evento.

    `negociacao` é o mapa já pronto (`mapa_de_negociacoes`) de quem chamou
    com todos os ids de uma vez -- a central do sino faz UMA caminhada pelas
    cadeias para os sete avisos de orçamento, e não uma por aviso.
    """
    if negociacao is not None:
        ids = {int(pk) for pk in orcamento_ids if pk}
        if ids <= negociacao.keys():
            return frozenset(negociacao[pk] for pk in ids)
    return frozenset(mapa_de_negociacoes(orcamento_ids).values())


def mapa_de_negociacoes(orcamento_ids, pais_conhecidos=None):
    """Cada versão -> a primeira versão da cadeia (a negociação).

    É o mesmo cálculo de `_grupos_de_versoes`, devolvendo de qual
    negociação cada id veio. A folha de propostas (seção 116) usa para
    mostrar UMA linha por negociação -- o mesmo número que o sino conta.

    `pais_conhecidos` ({versão: versão anterior}) são elos que quem chamou
    ACABOU de ler do banco na mesma requisição (a central lê o
    `orcamento_anterior` junto com as versões de cada aviso): não se
    pergunta de novo por eles. A caminhada só vai ao banco pelos elos que
    faltam, um nível por consulta -- o resultado é o mesmo de ler tudo.
    """
    originais = {int(pk) for pk in orcamento_ids if pk}
    if not originais:
        return {}

    pais = dict(pais_conhecidos or {})
    sumidos = set()

    def ponta(versao):
        """Até onde os elos já sabidos levam (com a mesma trava de ciclo)."""
        atual = versao
        vistos = set()
        while pais.get(atual) and atual not in vistos and len(vistos) < 50:
            vistos.add(atual)
            atual = pais[atual]
        return atual

    # Cinquenta também é o limite defensivo usado por cadeia_de_versoes.
    for _ in range(50):
        fronteira = {
            fim for fim in (ponta(original) for original in originais)
            if fim not in pais and fim not in sumidos
        }
        if not fronteira:
            break
        pares = dict(
            Orcamento.objects.filter(pk__in=fronteira).values_list(
                "pk", "orcamento_anterior_id",
            )
        )
        for pk in fronteira:
            if pk in pares:
                pais[pk] = pares[pk]
            else:
                sumidos.add(pk)

    return {original: ponta(original) for original in originais}


def _sem_contrato():
    """Quem já tem o contrato sai da fila das aprovadas.

    A parte da equipe está feita: o prazo vai na Cláusula 3ª e o link de
    assinatura sai do cartão. O documento substituído não conta.
    """
    return ~Exists(
        DocumentoAssinatura.objects
        .filter(orcamento_id=OuterRef("pk"))
        .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
    )


def consulta_do_aviso(user, chave, hoje=None, agora=None):
    """As VERSÕES que cada aviso comercial cobre, já na carteira de quem vê.

    Uma consulta só para os dois lados: o número do sino (`_orcamentos`,
    `_respostas_de_cliente`) e a lista da folha que resolve o aviso
    (`resolver_avisos.py`, seção 116). Se a regra de "a vencer" mudar,
    muda aqui, e a folha nunca mostra uma lista com outro tamanho que o
    número que a abriu.
    """
    hoje = hoje or timezone.localdate()
    agora = agora or timezone.now()

    if chave in ("orcamentos_em_aberto", "orcamentos_vencidos", "orcamentos_vencendo"):
        abertos = limitar_orcamentos(
            user,
            Orcamento.objects.filter(status__in=Orcamento.EM_ABERTO),
        )
        if chave == "orcamentos_vencidos":
            return abertos.filter(validade__lt=hoje)
        if chave == "orcamentos_vencendo":
            return abertos.filter(
                validade__gte=hoje,
                validade__lte=hoje + timedelta(days=DIAS_PARA_COBRAR),
            )
        return abertos

    if chave in ("orcamentos_aprovados", "orcamentos_recusados"):
        respondidos = limitar_orcamentos(
            user,
            Orcamento.objects.filter(
                respondido_em__gte=agora - timedelta(days=DIAS_DE_NOVIDADE),
            ),
        )
        if chave == "orcamentos_recusados":
            return respondidos.filter(status=Orcamento.Status.RECUSADO)
        # APROVADA QUE JÁ TEM CONTRATO NÃO PRECISA MAIS DE VOCÊ. O aviso
        # dizia "combine data e montagem" por sete dias, mesmo depois de o
        # prazo combinado e o contrato gerado -- e um aviso que não some
        # quando se faz o que ele pede ensina a ignorar o sino.
        return respondidos.filter(status=Orcamento.Status.APROVADO).filter(
            _sem_contrato()
        )

    raise KeyError(chave)


#: Os avisos comerciais que saem das versões de orçamento, na ordem das
#: colunas de `versoes_dos_avisos`.
CHAVES_COMERCIAIS = (
    "orcamentos_em_aberto",
    "orcamentos_vencidos",
    "orcamentos_vencendo",
    "orcamentos_aprovados",
    "orcamentos_recusados",
)


@dataclass(frozen=True)
class VersoesDosAvisos:
    """As versões de cada aviso comercial, lidas numa ida só ao banco."""

    por_chave: dict  # chave -> {versão: situação}
    pais: dict  # versão -> versão anterior (o elo da negociação)


def versoes_dos_avisos(user, hoje=None, agora=None):
    """As versões de TODOS os avisos comerciais, numa consulta só.

    ERAM CINCO CONSULTAS (mais uma caminhada pelas cadeias de versões para
    cada uma): em aberto, vencidos, a vencer, aprovados e recusados -- e
    cada consulta é uma viagem ao Supabase (~170 ms, LEIA-ME-V10 §120).
    Agora a REGRA continua sendo `consulta_do_aviso`, intocada: cada aviso
    vira um EXISTS(...) da própria consulta dele, e uma linha volta para
    cada versão que cai em pelo menos um aviso, com uma coluna por aviso e
    o `orcamento_anterior` junto (os elos da negociação, sem perguntar de
    novo). O pré-filtro (em aberto OU respondido na janela de novidade)
    só corta o que nenhum aviso comercial pode conter; os EXISTS decidem.
    """
    hoje = hoje or timezone.localdate()
    agora = agora or timezone.now()
    marcas = {
        f"_ls_aviso_{indice}": Exists(
            consulta_do_aviso(user, chave, hoje, agora).filter(pk=OuterRef("pk"))
        )
        for indice, chave in enumerate(CHAVES_COMERCIAIS)
    }
    alguma = Q()
    for nome in marcas:
        alguma |= Q(**{nome: True})
    linhas = (
        Orcamento.objects
        .filter(
            Q(status__in=Orcamento.EM_ABERTO)
            | Q(respondido_em__gte=agora - timedelta(days=DIAS_DE_NOVIDADE))
        )
        .annotate(**marcas)
        .filter(alguma)
        .order_by()
        .values_list("pk", "status", "orcamento_anterior_id", *marcas)
    )
    por_chave = {chave: {} for chave in CHAVES_COMERCIAIS}
    pais = {}
    for pk, situacao, anterior, *dentro in linhas:
        pais[pk] = anterior
        for chave, esta in zip(CHAVES_COMERCIAIS, dentro):
            if esta:
                por_chave[chave][pk] = situacao
    return VersoesDosAvisos(por_chave=por_chave, pais=pais)


def _orcamentos(user, hoje, versoes=None, negociacao=None):
    """Pendências comerciais, vencidas e a vencer.

    A bolinha de Orçamentos representa a fila inteira ainda não finalizada:
    rascunho, aguardando resposta e negociação. Validade decide a urgência,
    não se a proposta existe na fila. Por isso uma proposta válida por mais
    de três dias também precisa entrar no número do menu.

    Vencido é perda; a vencer ainda dá para salvar com um telefonema. Esses
    dois motivos continuam separados na central, mas a mesma negociação
    ocupa uma única unidade no total, inclusive quando já foi refeita.

    `versoes` e `negociacao` chegam prontos de `coletar` (uma consulta para
    todos os avisos comerciais); chamada sozinha, lê o que precisa.
    """
    if versoes is None:
        versoes = versoes_dos_avisos(user, hoje)

    # A situação de cada versão aberta: é dela que sai o "1 rascunho e 1
    # esperando o cliente" do detalhe, contado por negociação, como o número.
    situacao_por_versao = versoes.por_chave["orcamentos_em_aberto"]
    if negociacao is None:
        negociacao = mapa_de_negociacoes(
            set().union(*(versoes.por_chave[chave] for chave in CHAVES_COMERCIAIS[:3])),
            pais_conhecidos=versoes.pais,
        )
    em_aberto = _grupos_de_versoes(situacao_por_versao, negociacao)
    vencidos = _grupos_de_versoes(versoes.por_chave["orcamentos_vencidos"], negociacao)
    a_vencer = _grupos_de_versoes(versoes.por_chave["orcamentos_vencendo"], negociacao)

    avisos = []

    if em_aberto:
        quantidade = len(em_aberto)
        por_situacao = {}
        for versao, situacao in situacao_por_versao.items():
            por_situacao.setdefault(situacao, set()).add(negociacao[versao])
        rascunhos = len(por_situacao.get(Orcamento.Status.RASCUNHO, ()))
        esperando = len(por_situacao.get(Orcamento.Status.AGUARDANDO_RESPOSTA, ()))
        negociando = len(por_situacao.get(Orcamento.Status.EM_NEGOCIACAO, ()))
        partes = _lista_em_frase([
            _plural(rascunhos, "rascunho por enviar", "rascunhos por enviar") if rascunhos else "",
            _plural(esperando, "esperando o cliente", "esperando o cliente") if esperando else "",
            _plural(negociando, "em negociação", "em negociação") if negociando else "",
        ])
        avisos.append(Aviso(
            chave="orcamentos_em_aberto",
            titulo=(
                "Proposta em aberto"
                if quantidade == 1 else "Propostas em aberto"
            ),
            detalhe=(
                f"{partes[:1].upper()}{partes[1:]}. "
                "Reenvie, lembre o cliente ou registre a resposta."
            ),
            quantidade=quantidade,
            url=reverse("orcamentos_inner", urlconf=URLCONF),
            nivel="info",
            icone="bi-file-earmark-text",
            orcamentos=em_aberto,
            acao="Acompanhar",
        ))

    if vencidos:
        quantidade = len(vencidos)
        avisos.append(Aviso(
            chave="orcamentos_vencidos",
            titulo="Orçamento vencido" if quantidade == 1 else "Orçamentos vencidos",
            detalhe=(
                "Passou da validade sem resposta. Marque como expirada, "
                "registre a recusa ou faça uma versão nova."
            ),
            quantidade=quantidade,
            url=reverse("orcamentos_inner", urlconf=URLCONF),
            nivel="critico",
            icone="bi-calendar-x",
            orcamentos=vencidos,
            acao="Resolver",
        ))

    if a_vencer:
        quantidade = len(a_vencer)
        avisos.append(Aviso(
            chave="orcamentos_vencendo",
            titulo="Orçamento a vencer" if quantidade == 1 else "Orçamentos a vencer",
            detalhe=(
                f"Vence em até {DIAS_PARA_COBRAR} dias. Lembre o cliente "
                "agora, enquanto a proposta vale."
            ),
            quantidade=quantidade,
            url=reverse("orcamentos_inner", urlconf=URLCONF),
            nivel="atencao",
            icone="bi-hourglass-split",
            orcamentos=a_vencer,
            acao="Lembrar cliente",
        ))

    return avisos


def _respostas_de_cliente(user, agora, versoes=None, negociacao=None):
    """Cliente respondeu pela página pública e ninguém viu ainda.

    É o aviso mais importante da lista em termos de dinheiro: uma proposta
    aprovada que fica parada é uma venda esfriando.
    """
    if versoes is None:
        versoes = versoes_dos_avisos(user, agora=agora)
    if negociacao is None:
        negociacao = mapa_de_negociacoes(
            set(versoes.por_chave["orcamentos_aprovados"])
            | set(versoes.por_chave["orcamentos_recusados"]),
            pais_conhecidos=versoes.pais,
        )
    aprovados = _grupos_de_versoes(versoes.por_chave["orcamentos_aprovados"], negociacao)
    recusados = _grupos_de_versoes(versoes.por_chave["orcamentos_recusados"], negociacao)

    avisos = []

    if aprovados:
        quantidade = len(aprovados)
        avisos.append(Aviso(
            chave="orcamentos_aprovados",
            titulo="Proposta aprovada" if quantidade == 1 else "Propostas aprovadas",
            detalhe=(
                "O cliente aprovou pelo link. Combine o prazo de entrega e "
                "mande o contrato para assinar."
            ),
            quantidade=quantidade,
            url=reverse("orcamentos_inner", urlconf=URLCONF) + "?filtro=aprovados",
            nivel="novidade",
            icone="bi-patch-check",
            orcamentos=aprovados,
            acao="Combinar entrega",
        ))

    if recusados:
        quantidade = len(recusados)
        avisos.append(Aviso(
            chave="orcamentos_recusados",
            titulo="Proposta recusada" if quantidade == 1 else "Propostas recusadas",
            detalhe="Leia o motivo do cliente antes de fazer a versão nova.",
            quantidade=quantidade,
            url=reverse("orcamentos_inner", urlconf=URLCONF) + "?filtro=recusados",
            nivel="info",
            icone="bi-emoji-frown",
            orcamentos=recusados,
            acao="Ver motivos",
        ))

    return avisos


def versao_atividades():
    """Último evento global; uma consulta mínima invalida caches entre workers.

    CARIMBADA PELO PULSO (LEIA-ME-V10, seção 120). O sino pergunta isto a
    cada 12 s em cada aba aberta -- uma viagem ao Supabase (~170 ms) para
    responder, quase sempre, o mesmo número. O pulso (`pulso.py`) já lê a
    contagem e o último `atualizado` das movimentações: movimentação nova
    muda o pulso, para todos os workers. Enquanto ele não muda, este número
    também não tem como mudar, e sai do cache. Sem pulso (banco fora do ar,
    tabela por migrar), lê na hora, como antes.
    """
    from django.core.cache import cache

    from .pulso import agora as pulso_agora

    carimbo = pulso_agora()
    chave = f"interno:versao_atividades:v1:{carimbo}" if carimbo else ""
    if chave:
        guardada = cache.get(chave)
        if guardada is not None:
            return guardada
    try:
        versao = (
            AtividadeOrcamento.objects.order_by("-id")
            .values_list("id", flat=True)
            .first()
            or 0
        )
    except DatabaseError:
        # Implantação entre o reinício e o migrate: o sino antigo continua
        # funcionando, e uma tabela nova nunca derruba o painel com 502.
        return 0
    if chave:
        cache.set(chave, versao, 120)
    return versao


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


def _atividades_pendentes(user):
    """As movimentações de colegas depois da última leitura -- e de quais versões.

    A leitura (EstadoNotificacao) entra como subconsulta, e não como uma
    ida ao banco à parte. Devolve (consulta, ids das versões) ou None se a
    tabela ainda não existe (implantação entre o reinício e o migrate).
    """
    try:
        lido = Coalesce(
            Subquery(
                EstadoNotificacao.objects.filter(
                    usuario=user,
                    chave=CHAVE_ATIVIDADE_LIDA,
                ).order_by("pk").values("quantidade")[:1],
                output_field=IntegerField(),
            ),
            Value(0),
        )
        # A permissão da lista também limita a notificação. Um vendedor não
        # descobre pelo sino uma proposta que a própria tela esconderia dele.
        visiveis = limitar_orcamentos(
            user,
            Orcamento.objects.all(),
        ).values("pk")
        pendentes = (
            AtividadeOrcamento.objects
            .filter(pk__gt=lido, orcamento_id__in=visiveis)
            .exclude(autor=user)
        )
        versoes = set(
            pendentes.order_by().values_list("orcamento_id", flat=True).distinct()
        )
    except DatabaseError:
        return None
    return pendentes, versoes


def _atividades_orcamento(user, pendencias=None, negociacao=None):
    """O que OUTRA pessoa fez e este usuário ainda não abriu no sino."""
    try:
        if pendencias is None:
            pendencias = _atividades_pendentes(user)
        if pendencias is None:
            return []
        pendentes, versoes = pendencias
        grupos = _grupos_de_versoes(versoes, negociacao)
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
        AtividadeOrcamento.Tipo.DOCUMENTO: "gerou o documento para assinatura do orçamento",
        AtividadeOrcamento.Tipo.ASSINATURA: "assinou o documento do orçamento",
        # LEIA-ME-V10, seção 104: o código digitado em Meus pedidos.
        AtividadeOrcamento.Tipo.VINCULADO: "vinculou à conta do site o orçamento",
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
        acao="Ver orçamentos",
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


def contar_juntos(consultas):
    """{nome: QuerySet} -> {nome: quantas linhas distintas}, numa ida só ao banco.

    Cada contagem da central era um `COUNT` com a sua viagem ao Supabase
    (~170 ms cada, LEIA-ME-V10 §120): pedidos, vendas, manutenções, O.S.,
    estoque, produção, projetos 3D e as quatro partes dos clientes
    incompletos. A consulta de cada uma continua sendo a MESMA (o QuerySet
    de sempre, com os filtros e junções dele); aqui elas só viajam juntas,
    cada uma como `(SELECT COUNT(*) FROM (<a consulta>))` num SELECT só.
    `values("pk").distinct()` é o `Count("pk", distinct=True)` de antes --
    e, nas que não têm junção, o mesmo número do `.count()`.
    """
    if not consultas:
        return {}
    partes = []
    parametros = []
    for indice, consulta in enumerate(consultas.values()):
        sql, valores = consulta.order_by().values("pk").distinct().query.sql_with_params()
        partes.append(f"(SELECT COUNT(*) FROM ({sql}) ls_contagem_{indice})")
        parametros.extend(valores)
    with connection.cursor() as cursor:
        cursor.execute("SELECT " + ", ".join(partes), parametros)
        linha = cursor.fetchone()
    return {nome: int(valor or 0) for nome, valor in zip(consultas, linha)}


def consultas_das_contagens(acesso):
    """As contagens da central que ESTA pessoa recebe, por nome (ver `coletar`)."""
    from core.models import PedidoProjeto3D
    from core.objetos_3d import tabela_pronta

    consultas = {}
    if acesso["clientes"]:
        sem_contato, sem_documento, sem_endereco = partes_incompletas()
        ativos = Cliente.objects.filter(ativo=True)
        consultas["clientes_total"] = ativos.filter(filtro_incompletos())
        consultas["clientes_contato"] = ativos.filter(sem_contato)
        consultas["clientes_documento"] = ativos.filter(sem_documento)
        consultas["clientes_endereco"] = ativos.filter(sem_endereco)
    if (acesso["vendas"] or acesso["gestao"]) and tabela_pronta(PedidoProjeto3D):
        consultas["projetos_3d"] = PedidoProjeto3D.objects.filter(status="novo")
    if acesso["operacao"]:
        if acesso["pedidos"]:
            consultas["pedidos"] = Pedido.objects.exclude(status__in=["finalizado", "cancelado"])
        if acesso["vendas_financeiro"]:
            consultas["vendas"] = Venda.objects.filter(confirmado=False)
        if acesso["manutencoes"]:
            consultas["manutencoes"] = Manutencao.objects.filter(status__in=["P", "A"])
        if acesso["ordens_servico"]:
            consultas["ordens_servico"] = OrdemServico.objects.filter(
                status__in=OrdemServico.PENDENTES,
                # Se houver dado legado inconsistente, somente a ponta atual da
                # cadeia ocupa a bolinha; v1/v2/v3 nunca viram três serviços.
                ordem_refeita__isnull=True,
            )
    if acesso["estoque"]:
        consultas["estoque"] = EstoqueMaterial.objects.criticos()
    if acesso["producao"]:
        consultas["producao"] = OrdemProducao.objects.exclude(
            status__in=[OrdemProducao.Status.CONCLUIDA, OrdemProducao.Status.CANCELADA]
        )
    return consultas


def _operacao(acesso, contagens=None):
    """Pendências operacionais sem revelar módulos fora da função."""
    avisos = []
    if contagens is None:
        contagens = contar_juntos({
            nome: consulta
            for nome, consulta in consultas_das_contagens(acesso).items()
            if nome in ("pedidos", "vendas", "manutencoes", "ordens_servico")
        })

    if acesso["pedidos"]:
        pedidos = contagens.get("pedidos", 0)
        if pedidos:
            avisos.append(Aviso(
                chave="pedidos",
                titulo="Pedido em aberto" if pedidos == 1 else "Pedidos em aberto",
                detalhe=(
                    "Ainda não finalizados nem cancelados. Atualize o "
                    "andamento de cada um sem sair daqui."
                ),
                quantidade=pedidos,
                url=reverse("pedidos_inner", urlconf=URLCONF),
                nivel="info",
                icone="bi-box2-heart",
                acao="Atualizar andamento",
            ))

    if acesso["vendas_financeiro"]:
        vendas = contagens.get("vendas", 0)
        if vendas:
            avisos.append(Aviso(
                chave="vendas",
                titulo="Venda a confirmar" if vendas == 1 else "Vendas a confirmar",
                detalhe="Pagamento registrado, confirmação pendente. Confira na tela de Vendas.",
                quantidade=vendas,
                url=reverse("vendas_inner", urlconf=URLCONF),
                nivel="atencao",
                icone="bi-receipt",
                acao="Conferir vendas",
            ))

    if acesso["manutencoes"]:
        manutencoes = contagens.get("manutencoes", 0)
        if manutencoes:
            avisos.append(Aviso(
                chave="manutencoes",
                titulo="Manutenção aberta" if manutencoes == 1 else "Manutenções abertas",
                detalhe="Chamado do cliente esperando resposta. Faça a triagem.",
                quantidade=manutencoes,
                url=reverse("manutencao_inner", urlconf=URLCONF),
                nivel="atencao",
                icone="bi-wrench-adjustable",
                acao="Atender",
            ))

    if acesso["ordens_servico"]:
        ordens = contagens.get("ordens_servico", 0)
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
                acao="Abrir O.S.",
            ))

    return avisos


def _estoque(criticos=None):
    """Material no mínimo ou abaixo dele.

    A regra mora em `EstoqueMaterialQuerySet.criticos()`, junto do
    modelo, para este módulo e as telas de estoque não terem cada um a
    sua versão do que é "no mínimo".
    """
    if criticos is None:
        criticos = EstoqueMaterial.objects.criticos().count()

    if not criticos:
        return []

    return [Aviso(
        chave="estoque",
        titulo="Material para repor",
        detalhe="No mínimo ou abaixo dele. Veja a lista de compra e dê entrada no estoque.",
        quantidade=criticos,
        url=reverse("estoque_inner", urlconf=URLCONF),
        nivel="critico",
        icone="bi-box-seam",
        acao="Ver o que comprar",
    )]


def _clientes_incompletos(numeros=None):
    """Cadastros que ainda não sustentam orçamento, contato e deslocamento.

    UMA consulta, com o total e o que falta em cada parte: o detalhe diz
    "falta CPF/CNPJ em 12, endereço em 5" em vez de "falta contato, CPF/CNPJ
    ou endereço" -- quem lê sabe o tamanho de cada conserto antes de abrir.
    As três partes são as mesmas de `filtro_incompletos`, e um cliente
    pode faltar em mais de uma (por isso as partes somam mais que o total).
    """
    if numeros is None:
        sem_contato, sem_documento, sem_endereco = partes_incompletas()
        numeros = (
            Cliente.objects
            .filter(ativo=True)
            .aggregate(
                total=Count("pk", filter=filtro_incompletos(), distinct=True),
                contato=Count("pk", filter=sem_contato, distinct=True),
                documento=Count("pk", filter=sem_documento, distinct=True),
                endereco=Count("pk", filter=sem_endereco, distinct=True),
            )
        )
    total = numeros["total"] or 0
    if not total:
        return []
    faltas = [
        (numeros["documento"], "CPF/CNPJ válido"),
        (numeros["endereco"], "endereço"),
        (numeros["contato"], "contato"),
    ]
    if total == 1:
        detalhe = "Falta " + _lista_em_frase(
            [rotulo for numero, rotulo in faltas if numero]
        ) + "."
    else:
        detalhe = "Falta " + _lista_em_frase(
            [f"{rotulo} em {numero}" for numero, rotulo in faltas if numero]
        ) + "."
    return [Aviso(
        chave="clientes_incompletos",
        titulo="Cadastro de cliente incompleto" if total == 1 else "Cadastros de clientes incompletos",
        detalhe=detalhe + " Complete aqui mesmo, um por um.",
        quantidade=total,
        url=reverse("clientes_inner", urlconf=URLCONF) + "?incompletos=1",
        nivel="atencao",
        icone="bi-person-exclamation",
        acao="Completar",
    )]


def _producao(user, gestor, total=None):
    if total is None:
        total = OrdemProducao.objects.exclude(
            status__in=[OrdemProducao.Status.CONCLUIDA, OrdemProducao.Status.CANCELADA]
        ).count()
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
        acao="Acompanhar",
    )]


def _projetos_3d(novos=None):
    """Os projetos que clientes montaram no site (/monte-seu-projeto/) e ninguém abriu ainda.

    Sem a tabela (a migração ainda não rodou), não avisa nada -- e não
    consulta de novo a cada página (core.objetos_3d.tabela_pronta).
    """
    from core.models import PedidoProjeto3D
    from core.objetos_3d import tabela_pronta

    if not tabela_pronta(PedidoProjeto3D):
        return []
    if novos is None:
        novos = PedidoProjeto3D.objects.filter(status="novo").count()
    if not novos:
        return []
    return [Aviso(
        chave="projetos_3d",
        titulo="Projeto 3D novo do site" if novos == 1 else "Projetos 3D novos do site",
        detalhe="O cliente montou o espaço em 3D e pediu o projeto. Abra e responda.",
        quantidade=novos,
        url=reverse("pedidos_projeto_3d", urlconf=URLCONF) + "?status=novo",
        nivel="novidade",
        icone="bi-badge-3d",
        acao="Ver projetos",
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
    agora = timezone.now()
    avisos = []

    # POUCAS IDAS AO BANCO, AS MESMAS REGRAS (LEIA-ME-V10, seção 120). Eram
    # ~22 consultas cada vez que o pulso mudava -- ou seja, depois de TODA
    # gravação, para cada pessoa com o painel aberto: ~3,7 s de Supabase.
    # Agora: as contagens numa consulta (`contar_juntos`), as versões dos
    # cinco avisos comerciais noutra (`versoes_dos_avisos`), as
    # movimentações de colegas noutra, e UMA caminhada pelas cadeias de
    # versões para todos os avisos de orçamento. Cada aviso continua
    # montado pela função dele, com a regra dele.
    contagens = contar_juntos(consultas_das_contagens(acesso))

    if acesso["orcamentos"]:
        versoes = versoes_dos_avisos(user, hoje, agora)
        pendencias = _atividades_pendentes(user)
        todas = set(versoes.pais)
        if pendencias is not None:
            todas |= pendencias[1]
        negociacao = mapa_de_negociacoes(todas, pais_conhecidos=versoes.pais)
        avisos += _atividades_orcamento(user, pendencias, negociacao)
        avisos += _orcamentos(user, hoje, versoes, negociacao)
        avisos += _respostas_de_cliente(user, agora, versoes, negociacao)

    if acesso["clientes"]:
        avisos += _clientes_incompletos({
            "total": contagens.get("clientes_total", 0),
            "contato": contagens.get("clientes_contato", 0),
            "documento": contagens.get("clientes_documento", 0),
            "endereco": contagens.get("clientes_endereco", 0),
        })

    if acesso["vendas"] or acesso["gestao"]:
        avisos += _projetos_3d(contagens.get("projetos_3d", 0))

    if acesso["operacao"]:
        avisos += _operacao(acesso, contagens)

    if acesso["estoque"]:
        avisos += _estoque(contagens.get("estoque", 0))

    if acesso["producao"]:
        # A função é engenharia/acompanhamento de produção, portanto vê a
        # fábrica inteira. A atribuição individual continua destacada nas
        # próprias ordens.
        avisos += _producao(user, True, contagens.get("producao", 0))

    avisos.sort(key=lambda a: (PESO.get(a.nivel, 9), -a.quantidade))
    return avisos
