from django.db import models

from core.models import Brinquedos, Pedido, Venda, ItemPedido


class Prime(models.Model):
    criacao = models.DateTimeField(auto_now_add=True, null=True)
    atualizado = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class EnderecoCliente(Prime):
    cep = models.CharField(max_length=18)
    endereco = models.CharField(max_length=120)
    numero = models.CharField(max_length=5)
    bairro = models.CharField(max_length=50)
    cidade = models.CharField(max_length=25)
    estado = models.CharField(max_length=20)

    latitude = models.DecimalField(
        max_digits=50, decimal_places=30, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=50, decimal_places=30, null=True, blank=True
    )

    def __str__(self):
        self.endereco

    class Meta:
        verbose_name = "Endereço do Cliente"
        verbose_name_plural = "Endereços dos Clientes"


class Cliente(Prime):
    nome_cliente = models.CharField(max_length=90)
    endereco = models.ForeignKey(EnderecoCliente, on_delete=models.SET_NULL, related_name='cliente', null=True)
    telefone = models.CharField(max_length=14)
    email = models.CharField(max_length=150)

    def __str__(self):
        self.nome_cliente

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"


class TipoMaterial(Prime):
    descricao = models.CharField(max_length=120)

    class Meta:
        verbose_name = "Tipo de Material"
        verbose_name_plural = "Tipos de Materiais"


class Material(Prime):
    nome_material = models.CharField(max_length=90)
    descricao = models.CharField(max_length=150, null=True)
    tipo_material = models.ForeignKey(TipoMaterial, on_delete=models.SET_NULL, related_name='material', null=True)
    brinquedos_associados = models.ForeignKey(Brinquedos, on_delete=models.SET_NULL, related_name='material', null=True)

    def __str__(self):
        self.nome_material

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "materiais"


class EstoqueMaterial(Prime):
    descricao_local = models.CharField(max_length=90)
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='estoque')
    quantidade = models.IntegerField(default=1)
    preco_fornecedor = models.DecimalField(decimal_places=2, max_digits=6)

    def __str__(self):
        self.descricao_local

    class Meta:
        verbose_name = "Estoque de Material"
        verbose_name_plural = "Estoque de Materiais"


class CentralPedidos(Prime):
    descricao_pedido = models.CharField(max_length=90)
    pedido = models.ForeignKey(Pedido, max_length=90, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        self.descricao_pedido

    class Meta:
        verbose_name = "Central de Pedido"
        verbose_name_plural = "Central de Vendas"


class CentralItemPedido(ItemPedido):
    descricao = models.CharField(max_length=90)


class CentralVendas(Venda):
    descricao_venda = models.CharField(max_length=90)

    def __str__(self):
        self.descricao_venda

    class Meta:
        verbose_name = "Central de Vendas"


class ComprasMensais(Prime):
    descricao_compra = models.CharField(max_length=120)
    material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True, related_name='compra')
    valor = models.DecimalField(decimal_places=2, max_digits=6)


class ItensCompra(Prime):
    materiais = models.ForeignKey(Material, related_name='itens_compra', on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        self.materiais.nome_material

class CategoriaDespesa(Prime):
    nome_categoria = models.CharField(max_length=120)

    def __str__(self):
        self.nome_categoria

    class Meta:
        verbose_name = "Categoria de Despesa"
        verbose_name_plural = "Categorias de Despesas"


class DespesasMensais(Prime):
    descricao_despesa = models.CharField(max_length=90)
    valor_despesa = models.DecimalField(decimal_places=2, max_digits=6)
    categoria_despesa = models.ForeignKey(CategoriaDespesa, on_delete=models.SET_NULL, related_name='despesas',
                                          null=True)

    def __str__(self):
        self.descricao_despesa

    class Meta:
        verbose_name = "Despesa Mensal"
        verbose_name_plural = "Despesas Mensais"


class FinanceiroMensal(Prime):
    descricao = models.CharField(max_length=90)
    despesas_mensais = models.ForeignKey(DespesasMensais, on_delete=models.SET_NULL, related_name='financeiro_mes', null=True)
    valor_liquido = models.DecimalField(max_digits=6, decimal_places=2)
    valor_bruto = models.DecimalField(max_digits=6, decimal_places=2)
    lucro = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        return self.descricao

    class Meta:
        verbose_name = "Financeiro Mensal"
        verbose_name_plural = "Financeiros Mensais"


