# sistem_interno/context_processors.py

# Importação direta dos modelos do app 'core'
from django.core.exceptions import ObjectDoesNotExist

from core.models import Venda, Pedido, Manutencao
from .models import OrdemProducao


def fab_counts(request):
    """
    Retorna contagens globais para os FABs do painel administrativo.
    """
    # Retorna vazio se não estiver logado ou não for da equipe (staff)
    if not request.user.is_authenticated:
        return {
            "count_vendas": 0,
            "count_pedidos": 0,
            "count_manutencao": 0,
            "count_producao": 0,
            "eh_gestor_interno": False,
        }

    try:
        eh_gestor = request.user.is_superuser or request.user.gerente.ativo
    except (AttributeError, ObjectDoesNotExist):
        eh_gestor = request.user.is_superuser

    if not (request.user.is_staff or eh_gestor):
        return {
            "count_vendas": 0,
            "count_pedidos": 0,
            "count_manutencao": 0,
            "count_producao": 0,
            "eh_gestor_interno": False,
        }

    # 1. Vendas não confirmadas
    # (Ajuste o filtro se sua lógica de "venda pendente" for diferente)
    count_vendas = Venda.objects.filter(confirmado=False).count()

    # 2. Pedidos ativos (Tudo que não foi finalizado nem cancelado)
    count_pedidos = Pedido.objects.exclude(
        status__in=['finalizado', 'cancelado']
    ).count()

    # 3. Manutenções que precisam de atenção
    # Sugestão: Pega 'P' (Pendente) e 'A' (Em Andamento/Aprovado)
    # Se quiser só pendente, deixe apenas ['P']
    count_manutencao = Manutencao.objects.filter(status__in=['P', 'A']).count()

    producoes = OrdemProducao.objects.exclude(
        status__in=[OrdemProducao.Status.CONCLUIDA, OrdemProducao.Status.CANCELADA]
    )
    if not eh_gestor:
        producoes = producoes.filter(colaborador=request.user)
    count_producao = producoes.count()

    return {
        "count_vendas": count_vendas,
        "count_pedidos": count_pedidos,
        "count_manutencao": count_manutencao,
        "count_producao": count_producao,
        "eh_gestor_interno": eh_gestor,

        # Opcional: booleanos para facilitar a lógica no template
        "tem_vendas_pendentes": count_vendas > 0,
        "tem_pedidos_ativos": count_pedidos > 0,
        "tem_manutencao_pendente": count_manutencao > 0,
        "tem_producao_pendente": count_producao > 0,
    }
