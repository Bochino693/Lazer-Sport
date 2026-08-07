from django.core.cache import cache
from django.db.models import Count, Q, Sum

from .models import (
    Carrinho,
    CategoriasBrinquedos,
    Estabelecimentos,
    Manutencao,
    Pedido,
)


CACHE_GLOBAL_SECONDS = 300


def categorias_globais(request):
    """
    Categorias do cabeçalho mudam pouco e não precisam consultar o banco
    em toda página pública. O cache curto mantém o menu responsivo sem
    deixar alterações do admin presas por muito tempo.
    """
    cache_key = "lazer_sport:categorias_header:v1"
    categorias = cache.get(cache_key)

    if categorias is None:
        categorias = list(
            CategoriasBrinquedos.objects
            .exclude(
                nome_categoria__icontains="competitivos"
            )
            .exclude(
                nome_categoria__icontains="kids"
            )
            .exclude(
                nome_categoria__icontains="famosos"
            )
            .exclude(
                nome_categoria__icontains="espaço esportivo kids"
            )
            .exclude(
                nome_categoria__icontains="espaço kids play"
            )
            .order_by("nome_categoria")
        )
        cache.set(
            cache_key,
            categorias,
            CACHE_GLOBAL_SECONDS,
        )

    return {
        "categorias_header": categorias
    }


def estabelecimentos_globais(request):
    cache_key = "lazer_sport:estabelecimentos_header:v1"
    estabelecimentos = cache.get(cache_key)

    if estabelecimentos is None:
        estabelecimentos = list(
            Estabelecimentos.objects.all()
        )
        cache.set(
            cache_key,
            estabelecimentos,
            CACHE_GLOBAL_SECONDS,
        )

    return {
        "estabelecimentos_globais": estabelecimentos
    }


def manutencao_notificacao(request):
    if not request.user.is_authenticated:
        return {}

    perfil = getattr(
        request.user,
        "perfil",
        None,
    )

    if not perfil:
        return {
            "manutencao_pendente": 0,
            "manutencao_andamento": 0,
            "manutencao_abertas": 0,
            "tem_manutencao": False,
        }

    totais = (
        Manutencao.objects
        .filter(usuario=perfil)
        .aggregate(
            pendentes=Count(
                "id",
                filter=Q(status="P"),
            ),
            em_andamento=Count(
                "id",
                filter=Q(status="A"),
            ),
        )
    )

    pendentes = totais["pendentes"] or 0
    em_andamento = totais["em_andamento"] or 0
    total_abertas = pendentes + em_andamento

    return {
        "manutencao_pendente": pendentes,
        "manutencao_andamento": em_andamento,
        "manutencao_abertas": total_abertas,
        "tem_manutencao": total_abertas > 0,
    }


def carrinho_context(request):
    if not request.user.is_authenticated:
        return {
            "carrinho_total_itens": 0,
            "mostrar_float_carrinho": False,
        }

    perfil = getattr(
        request.user,
        "perfil",
        None,
    )

    if not perfil:
        return {
            "carrinho_total_itens": 0,
            "mostrar_float_carrinho": False,
        }

    carrinho = (
        Carrinho.objects
        .filter(cliente=perfil)
        .only("id")
        .first()
    )

    if not carrinho:
        return {
            "carrinho_total_itens": 0,
            "mostrar_float_carrinho": False,
        }

    total_itens = (
        carrinho.itens
        .aggregate(
            total=Sum("quantidade")
        )
        .get("total")
        or 0
    )

    return {
        "carrinho_total_itens": total_itens,
        "mostrar_float_carrinho": total_itens > 0,
    }


def pedidos_ativos_context(request):
    if not request.user.is_authenticated:
        return {}

    perfil = getattr(
        request.user,
        "perfil",
        None,
    )

    if not perfil:
        return {}

    total = (
        Pedido.objects
        .filter(cliente=perfil)
        .exclude(
            status__in=[
                "cancelado",
                "finalizado",
            ]
        )
        .count()
    )

    return {
        "tem_pedidos_ativos": total > 0,
        "total_pedidos_ativos": total,
    }


def admin_alertas_context(request):
    if not request.user.is_authenticated:
        return {}

    if not request.user.is_staff:
        return {}

    pedidos_alerta = (
        Pedido.objects
        .filter(
            status__in=[
                "criado",
                "aguardando_pagamento",
                "pago",
                "em_preparacao",
            ]
        )
        .count()
    )

    manutencoes_alerta = (
        Manutencao.objects
        .filter(
            status__in=[
                "P",
                "A",
            ]
        )
        .count()
    )

    return {
        "pedidos_alerta": pedidos_alerta,
        "tem_pedidos_alerta": pedidos_alerta > 0,
        "manutencoes_alerta": manutencoes_alerta,
        "tem_manutencoes_alerta": manutencoes_alerta > 0,
    }
