"""O que cada tela de gestão mede, e de onde vem cada número (core/analises.py).

Só o que o banco tem de verdade. Onde o sistema não guarda data (evento e
projeto não têm "criado em"), a tela mede o que está ligado a eles -- os
brinquedos do evento, as montagens 3D do projeto -- e diz isso no aviso.

PERMISSÃO. Cada tipo pede as MESMAS funções da tela em que aparece
(sistema_interno/urls.py): quem não abre a tela de cupons também não lê os
números dos cupons pelo endereço JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from django.db.models import CharField, Count, F, Q, Sum, Value
from django.db.models.functions import Cast, Concat

from .analises import DINHEIRO, Fonte, Metrica, dinheiro_da_linha

#: O pedido que já é venda: pago e daí em diante (cancelado e aguardando ficam de fora).
PEDIDO_PAGO = ("pago", "em_preparacao", "saiu_entrega", "finalizado")


@dataclass
class Tipo:
    codigo: str
    rotulo: str
    singular: str
    funcoes: tuple
    metricas: list
    fontes: Callable
    modelo: object
    principal: str
    nomes: Callable | None = None
    somente_super: bool = False
    avisos: list = field(default_factory=list)
    destaques: Callable | None = None
    tem_objeto: bool = True


def _funcoes():
    from sistema_interno.permissoes import CRIACAO, FINANCEIRO, GESTAO, VENDAS

    return CRIACAO, FINANCEIRO, GESTAO, VENDAS


# ----------------------------------------------------------------------
# métricas reaproveitadas
# ----------------------------------------------------------------------

AVISO_REGISTRO = (
    "Visitas e idas ao carrinho passaram a ser registradas por hora com esta "
    "tela; antes disso o site só guardava o total de cliques de cada produto."
)

VISITAS = Metrica("visitas", "Visitas", "bi-eye", ajuda="Aberturas da página no site.")
CARRINHO = Metrica("carrinho", "No carrinho", "bi-cart-plus", ajuda="Unidades postas no carrinho (site e aplicativo).")
CURTIDAS = Metrica("curtidas", "Curtidas", "bi-heart", ajuda="Curtidas no site e no aplicativo.")
DESEJOS = Metrica("desejos", "Lista de desejos", "bi-bookmark-heart", ajuda="Entradas na lista de desejos.")
ORCAMENTOS = Metrica("orcamentos", "Em orçamentos", "bi-file-earmark-text", ajuda="Propostas criadas com o item (versões substituídas não contam).")
APROVADOS = Metrica("aprovados", "Aprovados", "bi-check2-circle", ajuda="Propostas com o item aprovadas pelo cliente (pela data da resposta).")
VALOR_APROVADO = Metrica("valor_aprovado", "Valor aprovado", "bi-cash-coin", "dinheiro", ajuda="Soma das linhas do item nas propostas aprovadas.")
PEDIDOS = Metrica("pedidos", "Pedidos", "bi-bag-check", ajuda="Pedidos pagos da loja com o item.")
RECEITA = Metrica("receita", "Receita", "bi-currency-dollar", "dinheiro", ajuda="Soma das linhas do item nos pedidos pagos.")


def _interacoes(alvo, objeto_ids=None):
    from .models import InteracaoPorHora

    consulta = InteracaoPorHora.objects.filter(alvo=alvo, evento__in=("visita", "carrinho"))
    if objeto_ids is not None:
        consulta = consulta.filter(objeto_id__in=objeto_ids)
    return Fonte(
        "interacoes", consulta, "hora", {"v": Sum("quantidade")},
        {("visita", "v"): "visitas", ("carrinho", "v"): "carrinho"},
        separar_por="evento", campo_objeto="objeto_id",
        registro=(alvo, ("visita", "carrinho")),
    )


def _favoritos(campo, objeto_ids=None):
    from .models import Favorito

    consulta = Favorito.objects.filter(**{f"{campo}__isnull": False})
    if objeto_ids is not None:
        consulta = consulta.filter(**{f"{campo}__in": objeto_ids})
    return Fonte(
        "favoritos", consulta, "criacao", {"v": Count("id")},
        {("curtida", "v"): "curtidas", ("desejo", "v"): "desejos"},
        separar_por="tipo", campo_objeto=f"{campo}_id",
    )


def _orcamentos_do_item(campo, objeto_ids=None):
    from sistema_interno.models import ItemOrcamento, Orcamento

    base = ItemOrcamento.objects.filter(**{f"{campo}__isnull": False})
    if objeto_ids is not None:
        base = base.filter(**{f"{campo}_id__in": objeto_ids})
    criados = base.exclude(orcamento__status=Orcamento.Status.SUBSTITUIDO)
    aprovados = base.filter(orcamento__status=Orcamento.Status.APROVADO)
    return [
        Fonte(
            "orcamentos", criados, "orcamento__criacao",
            {"n": Count("orcamento_id", distinct=True)}, {(None, "n"): "orcamentos"},
            campo_objeto=f"{campo}_id",
        ),
        Fonte(
            "aprovados", aprovados, "orcamento__respondido_em",
            {"n": Count("orcamento_id", distinct=True), "valor": dinheiro_da_linha()},
            {(None, "n"): "aprovados", (None, "valor"): "valor_aprovado"},
            campo_objeto=f"{campo}_id",
        ),
    ]


def _pedidos_do_item(tipo_item, objeto_ids=None):
    from .models import ItemPedido

    consulta = ItemPedido.objects.filter(tipo_item=tipo_item, pedido__status__in=PEDIDO_PAGO)
    if objeto_ids is not None:
        consulta = consulta.filter(object_id__in=objeto_ids)
    return Fonte(
        "pedidos", consulta, "pedido__criacao",
        {"n": Count("pedido_id", distinct=True), "valor": Sum("subtotal")},
        {(None, "n"): "pedidos", (None, "valor"): "receita"},
        campo_objeto="object_id",
    )


def _ids(objeto_id):
    return None if objeto_id is None else [objeto_id]


def _nomes(modelo, campo):
    def nomes(ids):
        validos = [i for i in ids if isinstance(i, int)]
        return dict(modelo.objects.filter(pk__in=validos).values_list("pk", campo))
    return nomes


# ----------------------------------------------------------------------
# brinquedo, peça, combo, promoção
# ----------------------------------------------------------------------

def _fontes_brinquedo(objeto_id):
    ids = _ids(objeto_id)
    return [
        _interacoes("brinquedo", ids),
        _favoritos("brinquedo", ids),
        *_orcamentos_do_item("brinquedo", ids),
        _pedidos_do_item("brinquedo", ids),
    ]


def _fontes_peca(objeto_id):
    ids = _ids(objeto_id)
    return [
        _interacoes("peca", ids),
        _favoritos("peca", ids),
        *_orcamentos_do_item("peca", ids),
        _pedidos_do_item("pecas", ids),
    ]


def _fontes_combo(objeto_id):
    ids = _ids(objeto_id)
    return [_interacoes("combo", ids), _pedidos_do_item("combo", ids)]


def _fontes_promocao(objeto_id):
    ids = _ids(objeto_id)
    return [_interacoes("promocao", ids), _pedidos_do_item("promocao", ids)]


# ----------------------------------------------------------------------
# cupom
# ----------------------------------------------------------------------

USOS = Metrica("usos", "Usos", "bi-ticket-perforated", ajuda="Pedidos pagos que usaram o cupom.")
DESCONTO = Metrica(
    "desconto", "Desconto concedido", "bi-percent", "dinheiro", subir_e_bom=None,
    ajuda="Quanto os pedidos pagos deixaram de cobrar pelo cupom.",
)
RECEITA_CUPOM = Metrica("receita", "Receita com cupom", "bi-currency-dollar", "dinheiro", ajuda="Total dos pedidos pagos com o cupom.")
RESGATES = Metrica("resgates", "Resgates por pontos", "bi-stars", ajuda="Cupons trocados por pontos na loja do aplicativo.", so_geral=True)


def _fontes_cupom(objeto_id):
    from .models import Cupom, Pedido, ResgateCupom

    pedidos = Pedido.objects.filter(status__in=PEDIDO_PAGO).exclude(cupom_codigo__isnull=True).exclude(cupom_codigo="")
    if objeto_id is not None:
        codigo = Cupom.objects.filter(pk=objeto_id).values_list("codigo", flat=True).first()
        pedidos = pedidos.filter(cupom_codigo__iexact=codigo) if codigo else pedidos.none()
    fontes = [
        Fonte(
            "pedidos_com_cupom", pedidos, "criacao",
            {"n": Count("id"), "desconto": Sum("valor_desconto"), "valor": Sum("total_final")},
            {(None, "n"): "usos", (None, "desconto"): "desconto", (None, "valor"): "receita"},
            campo_objeto="cupom_codigo",
        ),
    ]
    if objeto_id is None:
        fontes.append(Fonte("resgates", ResgateCupom.objects.all(), "criacao", {"n": Count("id")}, {(None, "n"): "resgates"}))
    return fontes


def _nomes_cupom(codigos):
    from .models import Cupom

    textos = [c for c in codigos if isinstance(c, str)]
    achados = {}
    for pk, codigo in Cupom.objects.filter(codigo__in=textos).values_list("pk", "codigo"):
        achados.setdefault(codigo, pk)
    return {codigo: {"id": achados.get(codigo), "nome": codigo} for codigo in textos}


# ----------------------------------------------------------------------
# evento: o que os brinquedos do evento fizeram
# ----------------------------------------------------------------------

def _brinquedos_de_eventos():
    from .models import Eventos

    mapa = {}
    for evento_id, brinquedo_id in Eventos.brinquedos.through.objects.values_list("eventos_id", "brinquedos_id"):
        mapa.setdefault(brinquedo_id, []).append(evento_id)
    return mapa


def _fontes_evento(objeto_id):
    from .models import Eventos

    if objeto_id is not None:
        ids = list(Eventos.brinquedos.through.objects.filter(eventos_id=objeto_id).values_list("brinquedos_id", flat=True))
        agrupar = None
    else:
        mapa = _brinquedos_de_eventos()
        ids = list(mapa)
        agrupar = lambda brinquedo_id: mapa.get(brinquedo_id, [])  # noqa: E731
    fontes = [_interacoes("brinquedo", ids), _favoritos("brinquedo", ids), _pedidos_do_item("brinquedo", ids)]
    for fonte in fontes:
        fonte.agrupar_ranking = agrupar
    return fontes


# ----------------------------------------------------------------------
# projeto
# ----------------------------------------------------------------------

PEDIDOS_3D = Metrica("pedidos_3d", "Pedidos “Monte seu projeto”", "bi-box-seam", ajuda="Espaços montados pelo cliente no site.", so_geral=True)
FECHADOS_3D = Metrica("fechados_3d", "Pedidos 3D fechados", "bi-patch-check", ajuda="Pedidos do “Monte seu projeto” marcados como fechados (pela data do pedido).", so_geral=True)
NOVOS_PROJETOS = Metrica("novos_projetos", "Projetos cadastrados", "bi-folder-plus", ajuda="Brinquedos projetados cadastrados no painel.", so_geral=True)
MONTAGENS = Metrica("montagens", "Montagens 3D", "bi-boxes", ajuda="Montagens feitas no laboratório 3D para o projeto.")


def _fontes_projeto(objeto_id):
    from .models import BrinquedosProjeto, MontagemTresD, PedidoProjeto3D, Projetos

    montagens = MontagemTresD.objects.filter(projeto__isnull=False)
    if objeto_id is not None:
        projetado = Projetos.objects.filter(pk=objeto_id).values_list("brinquedo_projetado_id", flat=True).first()
        montagens = montagens.filter(projeto_id=projetado or 0)
        return [Fonte("montagens", montagens, "criacao", {"n": Count("id")}, {(None, "n"): "montagens"})]
    mapa = dict(Projetos.objects.exclude(brinquedo_projetado__isnull=True).values_list("brinquedo_projetado_id", "pk"))
    return [
        Fonte(
            "pedidos_3d", PedidoProjeto3D.objects.all(), "criacao",
            {"n": Count("id"), "fechados": Count("id", filter=Q(status="fechado"))},
            {(None, "n"): "pedidos_3d", (None, "fechados"): "fechados_3d"},
        ),
        Fonte("novos_projetos", BrinquedosProjeto.objects.all(), "criacao", {"n": Count("id")}, {(None, "n"): "novos_projetos"}),
        Fonte(
            "montagens", montagens, "criacao", {"n": Count("id")}, {(None, "n"): "montagens"},
            campo_objeto="projeto_id",
            agrupar_ranking=lambda projetado: [mapa[projetado]] if projetado in mapa else [],
        ),
    ]


# ----------------------------------------------------------------------
# cliente (carteira do painel)
# ----------------------------------------------------------------------

NOVOS_CLIENTES = Metrica("novos", "Clientes novos", "bi-person-plus", ajuda="Cadastros novos na carteira.", so_geral=True)
PROPOSTAS = Metrica("orcamentos", "Orçamentos", "bi-file-earmark-text", ajuda="Propostas criadas (versões substituídas não contam).")
PROPOSTAS_APROVADAS = Metrica("aprovados", "Aprovados", "bi-check2-circle", ajuda="Propostas aprovadas (pela data da resposta).")
VALOR_PROPOSTAS = Metrica("valor_aprovado", "Valor aprovado", "bi-cash-coin", "dinheiro", ajuda="Total das propostas aprovadas: o valor fechado ou itens + frete − desconto.")
RECUSADOS = Metrica("recusados", "Recusados", "bi-x-circle", subir_e_bom=False, ajuda="Propostas recusadas (pela data da resposta).")


def _fontes_cliente(objeto_id):
    from sistema_interno.models import Cliente, ItemOrcamento, Orcamento

    orcamentos = Orcamento.objects.all()
    itens = ItemOrcamento.objects.all()
    if objeto_id is not None:
        orcamentos = orcamentos.filter(cliente_id=objeto_id)
        itens = itens.filter(orcamento__cliente_id=objeto_id)
    aprovado = Orcamento.Status.APROVADO
    respondidos = orcamentos.filter(status__in=(aprovado, Orcamento.Status.RECUSADO))
    fontes = [
        Fonte(
            "propostas", orcamentos.exclude(status=Orcamento.Status.SUBSTITUIDO), "criacao",
            {"n": Count("id")}, {(None, "n"): "orcamentos"}, campo_objeto="cliente_id",
        ),
        # O total da proposta é o valor fechado, quando existe; senão, itens + frete − desconto.
        # São três fontes somadas, para tudo continuar agrupado no banco.
        Fonte(
            "respostas", respondidos, "respondido_em",
            {
                "aprovados": Count("id", filter=Q(status=aprovado)),
                "recusados": Count("id", filter=Q(status=Orcamento.Status.RECUSADO)),
                "fechado": Sum("valor_final", filter=Q(status=aprovado, valor_final__isnull=False)),
                "ajuste": Sum(F("frete") - F("desconto"), output_field=DINHEIRO, filter=Q(status=aprovado, valor_final__isnull=True)),
            },
            {(None, "aprovados"): "aprovados", (None, "recusados"): "recusados", (None, "fechado"): "valor_aprovado", (None, "ajuste"): "valor_aprovado"},
            campo_objeto="cliente_id",
        ),
        Fonte(
            "itens_aprovados", itens.filter(orcamento__status=aprovado, orcamento__valor_final__isnull=True),
            "orcamento__respondido_em", {"valor": dinheiro_da_linha()}, {(None, "valor"): "valor_aprovado"},
            campo_objeto="orcamento__cliente_id",
        ),
    ]
    if objeto_id is None:
        fontes.append(Fonte("clientes", Cliente.objects.all(), "criacao", {"n": Count("id")}, {(None, "n"): "novos"}))
    return fontes


# ----------------------------------------------------------------------
# pedido (loja)
# ----------------------------------------------------------------------

PEDIDOS_CRIADOS = Metrica("criados", "Pedidos feitos", "bi-bag", ajuda="Todos os pedidos criados, pagos ou não.")
PEDIDOS_PAGOS = Metrica("pagos", "Pedidos pagos", "bi-bag-check", ajuda="Pagos e daí em diante (em preparação, entrega, finalizado).")
RECEITA_LOJA = Metrica("receita", "Receita", "bi-currency-dollar", "dinheiro", ajuda="Total final dos pedidos pagos (com frete).")
TICKET = Metrica("ticket", "Ticket médio", "bi-receipt", "dinheiro", ajuda="Receita ÷ pedidos pagos.", razao=("receita", "pagos"))
CANCELADOS = Metrica("cancelados", "Cancelados", "bi-x-octagon", subir_e_bom=False, ajuda="Pedidos cancelados ou com o Pix expirado.")
ITENS_VENDIDOS = Metrica("itens", "Itens vendidos", "bi-box2", ajuda="Unidades nos pedidos pagos.")


def _fontes_pedido(objeto_id):
    from .models import ItemPedido, Pedido

    pago = Q(status__in=PEDIDO_PAGO)
    return [
        Fonte(
            "pedidos", Pedido.objects.all(), "criacao",
            {
                "criados": Count("id"),
                "pagos": Count("id", filter=pago),
                "receita": Sum("total_final", filter=pago),
                "cancelados": Count("id", filter=Q(status="cancelado")),
            },
            {(None, "criados"): "criados", (None, "pagos"): "pagos", (None, "receita"): "receita", (None, "cancelados"): "cancelados"},
        ),
        Fonte(
            "itens", ItemPedido.objects.filter(pedido__status__in=PEDIDO_PAGO).exclude(object_id__isnull=True), "pedido__criacao",
            {"n": Sum("quantidade")}, {(None, "n"): "itens"},
            campo_objeto="item_chave",
            expressao_objeto=Concat("tipo_item", Value(":"), Cast("object_id", CharField())),
        ),
    ]


# ----------------------------------------------------------------------
# usuário (contas do site e do painel)
# ----------------------------------------------------------------------

CADASTROS = Metrica("cadastros", "Cadastros novos", "bi-person-plus", ajuda="Contas criadas no período (site, aplicativo, Google, Apple e painel).", so_geral=True)
ATIVOS = Metrica("ativos", "Contas ativas", "bi-activity", ajuda="Contas distintas que usaram o site, o aplicativo ou o painel.", so_geral=True)
PEDIDOS_CONTAS = Metrica("pedidos", "Pedidos pagos", "bi-bag-check", ajuda="Pedidos pagos feitos pelas contas.")
GASTO = Metrica("gasto", "Gasto na loja", "bi-currency-dollar", "dinheiro", ajuda="Total final dos pedidos pagos.")
FAVORITOS_CONTAS = Metrica("favoritos", "Curtidas e desejos", "bi-heart", ajuda="Curtidas e entradas na lista de desejos feitas com a conta logada.")
DIAS_DE_ACESSO = Metrica("acessos", "Dias com acesso", "bi-calendar-check", ajuda="Dias em que a conta usou o site, o aplicativo ou o painel.", so_objeto=True)
PONTOS = Metrica("pontos", "Pontos ganhos", "bi-stars", ajuda="Pontos do programa de fidelidade.", so_objeto=True)
JOGADAS_CONTAS = Metrica("jogadas", "Jogadas", "bi-controller", ajuda="Cada Jogar no portal de jogos feito com a conta logada (core/jogadas.py).")


# ----------------------------------------------------------------------
# jogo (portal Lazer & Sport Games): cada Jogar com data, JogadaRegistrada
# ----------------------------------------------------------------------

JOGADAS = Metrica("jogadas", "Jogadas", "bi-controller", ajuda="Cada Jogar (a mesma pessoa no mesmo jogo em até 3 min conta uma vez).")
JOGADORES = Metrica("com_conta", "Pessoas com conta", "bi-person-check", ajuda="Contas distintas que jogaram no período.")
VISITANTES = Metrica("visitantes", "Visitantes", "bi-incognito", ajuda="Visitantes sem conta distintos (um número da sessão, que não diz quem é).")
JOGADAS_EQUIPE = Metrica("equipe", "Jogadas da equipe", "bi-shield-lock", subir_e_bom=None, ajuda="Jogadas de contas da equipe (staff), que também contam nas jogadas.")


def _fontes_jogo(objeto_id):
    from .models import JogadaRegistrada, JogoCadastrado

    base = JogadaRegistrada.objects.all()
    if objeto_id is not None:
        slug = JogoCadastrado.objects.filter(pk=objeto_id).values_list("slug", flat=True).first()
        base = base.filter(jogo=slug) if slug else base.none()
    return [
        Fonte(
            "jogadas", base, "quando",
            {"n": Count("id"), "equipe": Count("id", filter=Q(equipe=True))},
            {(None, "n"): "jogadas", (None, "equipe"): "equipe"},
            campo_objeto="jogo",
        ),
        Fonte(
            "com_conta", base.filter(usuario__isnull=False), "quando",
            {"n": Count("usuario", distinct=True)}, {(None, "n"): "com_conta"}, aditiva=False,
        ),
        Fonte(
            "visitantes", base.filter(usuario__isnull=True).exclude(visitante=""), "quando",
            {"n": Count("visitante", distinct=True)}, {(None, "n"): "visitantes"}, aditiva=False,
        ),
    ]


def _nomes_jogo(slugs):
    """slug -> nome e, para os cadastrados pelo painel, o id (a ficha abre deles)."""
    from . import arena
    from .models import JogoCadastrado

    textos = [s for s in slugs if isinstance(s, str)]
    nomes = {j["slug"]: {"id": None, "nome": j["titulo"]} for j in arena.JOGOS if j["slug"] in textos}
    for pk, slug, nome in JogoCadastrado.objects.filter(slug__in=textos).values_list("pk", "slug", "nome"):
        nomes[slug] = {"id": pk, "nome": nome}
    return nomes


def _fontes_usuario(objeto_id):
    from django.contrib.auth.models import User

    from .models import AcessoDiario, Favorito, JogadaRegistrada, Pedido, PontoGanho

    pedidos = Pedido.objects.filter(status__in=PEDIDO_PAGO, cliente__user__isnull=False)
    favoritos = Favorito.objects.filter(usuario__isnull=False)
    if objeto_id is not None:
        return [
            Fonte(
                "pedidos", pedidos.filter(cliente__user_id=objeto_id), "criacao",
                {"n": Count("id"), "gasto": Sum("total_final")}, {(None, "n"): "pedidos", (None, "gasto"): "gasto"},
            ),
            Fonte("favoritos", favoritos.filter(usuario_id=objeto_id), "criacao", {"n": Count("id")}, {(None, "n"): "favoritos"}),
            Fonte(
                "acessos", AcessoDiario.objects.filter(usuario_id=objeto_id), "dia", {"n": Count("id")},
                {(None, "n"): "acessos"}, campo_e_data=True,
            ),
            Fonte(
                "pontos", PontoGanho.objects.filter(usuario_id=objeto_id, pontos__gt=0), "criacao",
                {"n": Sum("pontos")}, {(None, "n"): "pontos"},
            ),
            Fonte("jogadas", JogadaRegistrada.objects.filter(usuario_id=objeto_id), "quando", {"n": Count("id")}, {(None, "n"): "jogadas"}),
        ]
    return [
        Fonte("cadastros", User.objects.all(), "date_joined", {"n": Count("id")}, {(None, "n"): "cadastros"}),
        Fonte(
            "ativos", AcessoDiario.objects.all(), "dia", {"n": Count("usuario", distinct=True)},
            {(None, "n"): "ativos"}, aditiva=False, campo_e_data=True,
        ),
        Fonte(
            "pedidos", pedidos, "criacao", {"n": Count("id"), "gasto": Sum("total_final")},
            {(None, "n"): "pedidos", (None, "gasto"): "gasto"}, campo_objeto="cliente__user_id",
        ),
        Fonte("favoritos", favoritos, "criacao", {"n": Count("id")}, {(None, "n"): "favoritos"}, campo_objeto="usuario_id"),
        Fonte(
            "jogadas", JogadaRegistrada.objects.filter(usuario__isnull=False), "quando", {"n": Count("id")},
            {(None, "n"): "jogadas"}, campo_objeto="usuario_id",
        ),
    ]


def _nomes_usuario(ids):
    from django.contrib.auth.models import User

    validos = [i for i in ids if isinstance(i, int)]
    nomes = {}
    for pk, username, nome in User.objects.filter(pk__in=validos).values_list("pk", "username", "perfil__nome_completo"):
        nomes[pk] = nome or username
    return nomes


def _destaques_usuario():
    from .presenca import resumo

    numeros = resumo()
    return [
        {"codigo": "online", "rotulo": "Online agora", "valor": numeros["online"], "icone": "bi-broadcast", "tom": "bom"},
        {"codigo": "hoje", "rotulo": "Ativos hoje", "valor": numeros["hoje"], "icone": "bi-sun"},
        {"codigo": "semana", "rotulo": "Ativos em 7 dias", "valor": numeros["semana"], "icone": "bi-calendar-week"},
        {"codigo": "mes", "rotulo": "Ativos em 30 dias", "valor": numeros["mes"], "icone": "bi-calendar3"},
        {"codigo": "nunca", "rotulo": "Nunca entraram", "valor": numeros["nunca"], "icone": "bi-person-dash"},
    ]


def _nomes_item_pedido(chaves):
    """'tipo:id' -> o nome gravado no pedido (o produto pode ter mudado de nome)."""
    from .models import ItemPedido

    tipos_detalhe = {"brinquedo": "brinquedo", "combo": "combo", "promocao": "promocao", "pecas": "peca"}
    pares = []
    for chave in chaves:
        if isinstance(chave, str) and ":" in chave:
            tipo, _, pk = chave.partition(":")
            if pk.isdigit():
                pares.append((tipo, int(pk)))
    if not pares:
        return {}
    filtro = Q()
    for tipo, pk in pares:
        filtro |= Q(tipo_item=tipo, object_id=pk)
    nomes = {}
    for tipo, pk, nome in ItemPedido.objects.filter(filtro).order_by("-id").values_list("tipo_item", "object_id", "nome_item"):
        nomes.setdefault(f"{tipo}:{pk}", {"id": pk, "nome": nome, "tipo": tipos_detalhe.get(tipo)})
    return nomes


# ----------------------------------------------------------------------
# o catálogo de tipos
# ----------------------------------------------------------------------

def _tipos():
    from django.contrib.auth.models import User

    from sistema_interno.models import Cliente

    from .models import Brinquedos, Combos, Cupom, Eventos, JogoCadastrado, PecasReposicao, Pedido, Projetos, Promocoes

    CRIACAO, FINANCEIRO, GESTAO, VENDAS = _funcoes()
    produto = [VISITAS, CARRINHO, CURTIDAS, DESEJOS, ORCAMENTOS, APROVADOS, VALOR_APROVADO, PEDIDOS, RECEITA]
    return {
        "brinquedo": Tipo(
            "brinquedo", "Brinquedos", "brinquedo", (CRIACAO,), produto, _fontes_brinquedo, Brinquedos,
            "visitas", _nomes(Brinquedos, "nome_brinquedo"), avisos=[AVISO_REGISTRO],
        ),
        "peca": Tipo(
            "peca", "Peças de reposição", "peça", (CRIACAO,), produto, _fontes_peca, PecasReposicao,
            "visitas", _nomes(PecasReposicao, "nome"), avisos=[AVISO_REGISTRO],
        ),
        "combo": Tipo(
            "combo", "Combos", "combo", (CRIACAO,), [VISITAS, CARRINHO, PEDIDOS, RECEITA], _fontes_combo, Combos,
            "visitas", _nomes(Combos, "descricao"), avisos=[AVISO_REGISTRO],
        ),
        "promocao": Tipo(
            "promocao", "Promoções", "promoção", (CRIACAO,), [VISITAS, CARRINHO, PEDIDOS, RECEITA], _fontes_promocao, Promocoes,
            "visitas", _nomes(Promocoes, "descricao"), avisos=[AVISO_REGISTRO],
        ),
        "cupom": Tipo(
            "cupom", "Cupons", "cupom", (CRIACAO, GESTAO), [USOS, DESCONTO, RECEITA_CUPOM, RESGATES], _fontes_cupom, Cupom,
            "usos", _nomes_cupom,
            avisos=["O uso conta pelo código gravado no pedido pago (o pedido guarda o código do momento da compra)."],
        ),
        "evento": Tipo(
            "evento", "Eventos", "evento", (CRIACAO,),
            [
                Metrica("visitas", "Visitas aos brinquedos", "bi-eye", ajuda="Visitas às páginas dos brinquedos do evento."),
                Metrica("curtidas", "Curtidas dos brinquedos", "bi-heart"),
                Metrica("pedidos", "Pedidos dos brinquedos", "bi-bag-check"),
                Metrica("receita", "Receita dos brinquedos", "bi-currency-dollar", "dinheiro"),
            ],
            _fontes_evento, Eventos, "visitas", _nomes(Eventos, "titulo"),
            avisos=["O evento não guarda data própria: os números são dos brinquedos ligados a cada evento.", AVISO_REGISTRO],
        ),
        "projeto": Tipo(
            "projeto", "Projetos", "projeto", (CRIACAO,), [PEDIDOS_3D, FECHADOS_3D, NOVOS_PROJETOS, MONTAGENS], _fontes_projeto, Projetos,
            "pedidos_3d", _nomes(Projetos, "titulo"),
            avisos=["A página do projeto no site não tem contador de visitas: aqui entram os pedidos do “Monte seu projeto” e as montagens 3D."],
        ),
        "cliente": Tipo(
            "cliente", "Clientes", "cliente", (VENDAS, GESTAO),
            [NOVOS_CLIENTES, PROPOSTAS, PROPOSTAS_APROVADAS, VALOR_PROPOSTAS, RECUSADOS], _fontes_cliente, Cliente,
            "orcamentos", _nomes(Cliente, "nome_cliente"),
        ),
        "pedido": Tipo(
            "pedido", "Pedidos da loja", "pedido", (FINANCEIRO, GESTAO),
            [PEDIDOS_CRIADOS, PEDIDOS_PAGOS, RECEITA_LOJA, TICKET, CANCELADOS, ITENS_VENDIDOS], _fontes_pedido, Pedido,
            "receita", _nomes_item_pedido, tem_objeto=False,
        ),
        "jogo": Tipo(
            "jogo", "Jogos", "jogo", (), [JOGADAS, JOGADORES, VISITANTES, JOGADAS_EQUIPE], _fontes_jogo, JogoCadastrado,
            "jogadas", _nomes_jogo, somente_super=True,
            avisos=["As jogadas antes da coleta com data (LEIA-ME 77) não entram: o período começa a contar a partir dela."],
        ),
        "usuario": Tipo(
            "usuario", "Usuários", "usuário", (),
            [CADASTROS, ATIVOS, DIAS_DE_ACESSO, PEDIDOS_CONTAS, GASTO, FAVORITOS_CONTAS, JOGADAS_CONTAS, PONTOS],
            _fontes_usuario, User, "cadastros", _nomes_usuario, somente_super=True, destaques=_destaques_usuario,
            avisos=["“Ativas” conta quem deu sinal de vida desde a seção 76 do LEIA-ME; antes disso só existia o último login."],
        ),
    }


_CACHE_TIPOS = {}


def tipos():
    if not _CACHE_TIPOS:
        _CACHE_TIPOS.update(_tipos())
    return _CACHE_TIPOS


def tipo(codigo):
    return tipos().get((codigo or "").strip().lower())
