# sistem_interno/context_processors.py

# Importação direta dos modelos do app 'core'
from core.models import Venda, Pedido, Manutencao


def fab_counts(request):
    """
    Retorna contagens globais para os FABs do painel administrativo.
    """
    # Retorna vazio se não estiver logado ou não for da equipe (staff)
    if not request.user.is_authenticated or not request.user.is_staff:
        return {
            "count_vendas": 0,
            "count_pedidos": 0,
            "count_manutencao": 0,
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

    return {
        "count_vendas": count_vendas,
        "count_pedidos": count_pedidos,
        "count_manutencao": count_manutencao,

        # Opcional: booleanos para facilitar a lógica no template
        "tem_vendas_pendentes": count_vendas > 0,
        "tem_pedidos_ativos": count_pedidos > 0,
        "tem_manutencao_pendente": count_manutencao > 0,
    }