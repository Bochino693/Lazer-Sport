# core/context_processors.py
#
# Refatoração de performance
# ==========================
# Problema original: os processors globais (categorias_globais,
# estabelecimentos_globais, clientes_rodape) rodavam em TODA request,
# inclusive de visitante anônimo e de bot. Como o base.html usa os três,
# cada pageview do site batia no Supabase 3x só pra montar header e rodapé.
#
# Duas mudanças aqui:
#
# 1) CACHE. Esses três dados mudam raramente (categoria, estabelecimento,
#    logo de cliente). Ficam em cache por 10 min. Um bot varrendo 5.000
#    URLs passa a gerar ~3 queries no total em vez de ~15.000.
#
# 2) LAZY. Os processors de usuário logado (carrinho, pedidos, manutenção,
#    alertas de admin) agora devolvem SimpleLazyObject: a query só dispara
#    se o template realmente imprimir a variável. Antes, .count() e
#    .exists() executavam sempre, mesmo em página que não mostra o badge.
#
# Também juntei queries duplicadas:
#   - manutencao_notificacao fazia 2 counts -> agora 1 query com aggregate
#   - pedidos_ativos_context fazia .exists() + .count() -> agora 1 count
#
# IMPORTANTE: pra invalidar o cache depois de mexer em categoria/
# estabelecimento/cliente no admin, chame limpar_cache_global() no save()
# do model (ou espere os 10 min).

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils.functional import SimpleLazyObject

from .models import (
    Carrinho,
    CategoriasBrinquedos,
    Clientes,
    Estabelecimentos,
    Manutencao,
    Pedido,
)

# 10 minutos. Aumente à vontade se o conteúdo do header/rodapé é estável.
TTL_GLOBAL = 60 * 10

CHAVE_CATEGORIAS = "ctx:categorias_header:v1"
CHAVE_ESTABELECIMENTOS = "ctx:estabelecimentos_globais:v1"
CHAVE_CLIENTES_RODAPE = "ctx:clientes_rodape:v1"

_CATEGORIAS_OCULTAS = (
    "competitivos",
    "kids",
    "famosos",
    "espaço esportivo kids",
    "espaço kids play",
)


def limpar_cache_global():
    """Chame isto no save()/delete() de CategoriasBrinquedos,
    Estabelecimentos e Clientes pra o header/rodapé atualizar na hora."""
    cache.delete_many([
        CHAVE_CATEGORIAS,
        CHAVE_ESTABELECIMENTOS,
        CHAVE_CLIENTES_RODAPE,
    ])


# ============================================================
# GLOBAIS (todo visitante) -- servidos do cache
# ============================================================

def categorias_globais(request):
    def _buscar():
        dados = cache.get(CHAVE_CATEGORIAS)
        if dados is None:
            filtro = Q()
            for termo in _CATEGORIAS_OCULTAS:
                filtro |= Q(nome_categoria__icontains=termo)

            # list() força a avaliação: o cache precisa guardar os
            # objetos, não o QuerySet preguiçoso.
            dados = list(
                CategoriasBrinquedos.objects
                .exclude(filtro)
                .only("id", "nome_categoria", "imagem_categoria")
                .order_by("nome_categoria")
            )
            cache.set(CHAVE_CATEGORIAS, dados, TTL_GLOBAL)
        return dados

    return {"categorias_header": SimpleLazyObject(_buscar)}


def estabelecimentos_globais(request):
    def _buscar():
        dados = cache.get(CHAVE_ESTABELECIMENTOS)
        if dados is None:
            dados = list(Estabelecimentos.objects.all())
            cache.set(CHAVE_ESTABELECIMENTOS, dados, TTL_GLOBAL)
        return dados

    return {"estabelecimentos_globais": SimpleLazyObject(_buscar)}


def clientes_rodape(request):
    """Seis primeiros clientes ativos com logo, para o base.html."""
    def _buscar():
        dados = cache.get(CHAVE_CLIENTES_RODAPE)
        if dados is None:
            dados = list(
                Clientes.objects
                .filter(ativo=True)
                .exclude(logo_cliente__isnull=True)
                .exclude(logo_cliente="")
                .only(
                    "id",
                    "descricao_cliente",
                    "logo_cliente",
                    "criacao",
                )
                .order_by("-criacao", "-id")[:6]
            )
            cache.set(CHAVE_CLIENTES_RODAPE, dados, TTL_GLOBAL)
        return dados

    return {"clientes_rodape": SimpleLazyObject(_buscar)}


# ============================================================
# POR USUÁRIO -- lazy, só consulta se o template usar
# ============================================================

def manutencao_notificacao(request):
    if not request.user.is_authenticated:
        return {}

    vazio = {
        "manutencao_pendente": 0,
        "manutencao_andamento": 0,
        "manutencao_abertas": 0,
        "tem_manutencao": False,
    }

    def _contar():
        perfil = getattr(request.user, "perfil", None)
        if not perfil:
            return vazio

        # Uma query só, em vez de dois .count() separados.
        agg = Manutencao.objects.filter(usuario=perfil).aggregate(
            pendentes=Count("id", filter=Q(status="P")),
            andamento=Count("id", filter=Q(status="A")),
        )
        pendentes = agg["pendentes"] or 0
        andamento = agg["andamento"] or 0
        total = pendentes + andamento

        return {
            "manutencao_pendente": pendentes,
            "manutencao_andamento": andamento,
            "manutencao_abertas": total,
            "tem_manutencao": total > 0,
        }

    dados = SimpleLazyObject(_contar)
    return {chave: SimpleLazyObject(lambda c=chave: dados[c]) for chave in vazio}


def carrinho_context(request):
    if not request.user.is_authenticated:
        return {
            "carrinho_total_itens": 0,
            "mostrar_float_carrinho": False,
        }

    def _total():
        perfil = getattr(request.user, "perfil", None)
        if not perfil:
            return 0

        carrinho = (
            Carrinho.objects
            .filter(cliente=perfil)
            .only("id")
            .first()
        )
        if not carrinho:
            return 0

        return carrinho.itens.aggregate(
            total=Sum("quantidade")
        )["total"] or 0

    total = SimpleLazyObject(_total)

    return {
        "carrinho_total_itens": total,
        "mostrar_float_carrinho": SimpleLazyObject(lambda: total > 0),
    }


def pedidos_ativos_context(request):
    if not request.user.is_authenticated:
        return {}

    def _contar():
        perfil = getattr(request.user, "perfil", None)
        if not perfil:
            return 0

        # Antes: .exists() + .count() = 2 queries. Agora 1.
        return (
            Pedido.objects
            .filter(cliente=perfil)
            .exclude(status__in=["cancelado", "finalizado"])
            .count()
        )

    total = SimpleLazyObject(_contar)

    return {
        "tem_pedidos_ativos": SimpleLazyObject(lambda: total > 0),
        "total_pedidos_ativos": total,
    }


def admin_alertas_context(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    def _pedidos():
        return Pedido.objects.filter(
            status__in=[
                "criado",
                "aguardando_pagamento",
                "pago",
                "em_preparacao",
            ]
        ).count()

    def _manutencoes():
        return Manutencao.objects.filter(status__in=["P", "A"]).count()

    pedidos = SimpleLazyObject(_pedidos)
    manutencoes = SimpleLazyObject(_manutencoes)

    return {
        "pedidos_alerta": pedidos,
        "tem_pedidos_alerta": SimpleLazyObject(lambda: pedidos > 0),
        "manutencoes_alerta": manutencoes,
        "tem_manutencoes_alerta": SimpleLazyObject(lambda: manutencoes > 0),
    }

# ============================================================
# APP ANDROID -- sem banco, só configuração
# ============================================================

def app_android(request):
    """Alimenta a caixa de download do app no rodapé.

    Não toca no banco: lê apenas as variáveis de ambiente. Enquanto nenhum
    link estiver publicado, `app_android_disponivel` é False e o rodapé mostra
    o estado "em produção" no mesmo espaço, sem quebrar o layout.
    """
    play = getattr(settings, "APP_ANDROID_PLAY_URL", "")
    apk = getattr(settings, "APP_ANDROID_APK_URL", "")

    return {
        "app_android_play_url": play,
        "app_android_apk_url": apk,
        "app_android_versao": getattr(settings, "APP_ANDROID_VERSAO", ""),
        "app_android_disponivel": bool(play or apk),
    }
