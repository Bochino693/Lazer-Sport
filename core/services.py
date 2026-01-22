from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from core.models import Pedido, ItemPedido, Carrinho


def criar_pedido_a_partir_do_carrinho(carrinho: Carrinho) -> Pedido:
    """
    Cria um Pedido e seus ItemPedido a partir de um Carrinho existente.
    NÃO remove o carrinho (fase parcial).
    """

    cliente = carrinho.cliente
    if not cliente:
        raise ValueError("Carrinho sem cliente associado")

    # 1️⃣ Cria o pedido (snapshot financeiro)
    pedido = Pedido.objects.create(
        cliente=cliente,
        status='criado',
        total_bruto=carrinho.total_bruto,
        valor_desconto=carrinho.valor_desconto,
        total_liquido=carrinho.total_liquido,
        cupom_codigo=carrinho.cupom.codigo if carrinho.cupom else None,
        cupom_percentual=carrinho.cupom.desconto_percentual if carrinho.cupom else None,
    )

    # 2️⃣ Copia os itens do carrinho
    for item in carrinho.itens.select_related('content_type'):
        ItemPedido.objects.create(
            pedido=pedido,
            content_type=item.content_type,
            object_id=item.object_id,
            nome_item=str(item.item),
            tipo_item=(
                'brinquedo'
                if item.content_type.model == 'brinquedos'
                else 'combo'
                if item.content_type.model == 'combos'
                else 'promocao'
            ),
            preco_unitario=item.preco_unitario,
            quantidade=item.quantidade,
            subtotal=item.subtotal,
        )

    return pedido
