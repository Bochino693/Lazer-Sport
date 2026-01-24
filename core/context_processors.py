from .models import CategoriasBrinquedos, Estabelecimentos, Manutencao, Carrinho


def categorias_globais(request):
    return {
        "categorias_header": CategoriasBrinquedos.objects.all().order_by("nome_categoria")
    }


def estabelecimentos_globais(request):
    return {
        "estabelecimentos_globais": Estabelecimentos.objects.all()
    }


def manutencao_notificacao(request):
    if not request.user.is_authenticated:
        return {}

    # Usa getattr para evitar erro caso o Perfil não tenha sido criado ainda
    perfil = getattr(request.user, 'perfil', None)

    if not perfil:
        return {
            'manutencao_pendente': 0,
            'manutencao_andamento': 0,
            'manutencao_abertas': 0,
            'tem_manutencao': False
        }

    manutencoes = Manutencao.objects.filter(usuario=perfil)

    pendentes = manutencoes.filter(status='P').count()
    em_andamento = manutencoes.filter(status='A').count()
    total_abertas = pendentes + em_andamento

    return {
        'manutencao_pendente': pendentes,
        'manutencao_andamento': em_andamento,
        'manutencao_abertas': total_abertas,
        'tem_manutencao': total_abertas > 0
    }

from django.db.models import Sum


def carrinho_context(request):
    if not request.user.is_authenticated:
        return {
            'carrinho_total_itens': 0,
            'mostrar_float_carrinho': False
        }

    # Usuário logado mas sem perfil ainda
    if not hasattr(request.user, 'perfil'):
        return {
            'carrinho_total_itens': 0,
            'mostrar_float_carrinho': False
        }

    cliente = request.user.perfil

    carrinho = Carrinho.objects.filter(cliente=cliente).first()

    if not carrinho:
        return {
            'carrinho_total_itens': 0,
            'mostrar_float_carrinho': False
        }

    total_itens = carrinho.itens.aggregate(
        total=Sum('quantidade')
    )['total'] or 0

    return {
        'carrinho_total_itens': total_itens,
        'mostrar_float_carrinho': total_itens > 0
    }


from .models import Pedido

def pedidos_ativos_context(request):
    if not request.user.is_authenticated:
        return {}

    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return {}

    pedidos_ativos = Pedido.objects.filter(
        cliente=perfil
    ).exclude(
        status__in=['cancelado', 'finalizado']
    )

    return {
        'tem_pedidos_ativos': pedidos_ativos.exists(),
        'total_pedidos_ativos': pedidos_ativos.count()
    }
