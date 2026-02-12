# core/context_processors.py
from core.models import Venda, Pedido, Manutencao

def fab_counts(request):
    """
    Retorna contagens para os FABs (Floating Action Buttons):
    - vendas: registros rápidos
    - pedidos: pedidos do site não finalizados ou cancelados
    - manutencao: manutenções pendentes
    """
    if request.user.is_authenticated:
        # Vendas que ainda não foram confirmadas
        count_vendas = Venda.objects.filter(confirmado=False).count()

        # Pedidos que ainda não estão finalizados ou cancelados
        count_pedidos = Pedido.objects.exclude(status__in=['finalizado', 'cancelado']).count()

        # Manutenções pendentes (status 'P' = pendente)
        count_manutencao = Manutencao.objects.filter(status='P').count()

        return {
            "count_vendas": count_vendas,
            "count_pedidos": count_pedidos,
            "count_manutencao": count_manutencao,
        }

    return {
        "count_vendas": 0,
        "count_pedidos": 0,
        "count_manutencao": 0,
    }
