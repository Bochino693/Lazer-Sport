from django.contrib import admin
from .models import Material, TipoMaterial, Gerente


@admin.register(Gerente)
class GerenteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'user', 'ativo')
    search_fields = ('nome', 'user__username', 'user__email')

@admin.register(TipoMaterial)
class TipoMaterial(admin.ModelAdmin):
    list_display = ('descricao', 'criacao')
    search_fields = ('descricao',)

    ordering = ('id',)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('nome_material', 'criacao')
    search_fields = ('nome_material',)

    ordering = ('id',)


from .models import (
    Cliente, EnderecoCliente, Setores, EstoqueMaterial,
    CentralPedidos, CentralVendas, ComprasMensais, ItensCompra,
    CategoriaDespesa, DespesasMensais, FinanceiroMensal
)

# Inline para endereços dentro do Cliente
class EnderecoClienteInline(admin.StackedInline):
    model = EnderecoCliente
    extra = 1

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome_cliente', 'telefone', 'email', 'criacao')
    search_fields = ('nome_cliente', 'email', 'telefone')
    inlines = [EnderecoClienteInline]

@admin.register(Setores)
class SetoresAdmin(admin.ModelAdmin):
    list_display = ('nome_setor', 'criacao')

@admin.register(EstoqueMaterial)
class EstoqueMaterialAdmin(admin.ModelAdmin):
    list_display = ('material', 'descricao_local', 'quantidade', 'preco_fornecedor')
    list_filter = ('descricao_local', 'material')
    search_fields = ('material__nome_material', 'descricao_local')

@admin.register(CentralPedidos)
class CentralPedidosAdmin(admin.ModelAdmin):
    list_display = ('descricao_pedido', 'status', 'criacao')
    list_filter = ('status',)
    search_fields = ('descricao_pedido',)

@admin.register(CentralVendas)
class CentralVendasAdmin(admin.ModelAdmin):
    list_display = ('id', 'origem', 'criacao')
    list_filter = ('origem',)

# Inline para itens dentro da compra
class ItensCompraInline(admin.TabularInline):
    model = ItensCompra
    extra = 1

@admin.register(ComprasMensais)
class ComprasMensaisAdmin(admin.ModelAdmin):
    list_display = ('descricao_compra', 'valor', 'criacao')
    inlines = [ItensCompraInline]

@admin.register(CategoriaDespesa)
class CategoriaDespesaAdmin(admin.ModelAdmin):
    list_display = ('nome_categoria',)

@admin.register(DespesasMensais)
class DespesasMensaisAdmin(admin.ModelAdmin):
    list_display = ('descricao_despesa', 'categoria_despesa', 'valor_despesa', 'criacao')
    list_filter = ('categoria_despesa',)
    search_fields = ('descricao_despesa',)

@admin.register(FinanceiroMensal)
class FinanceiroMensalAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'mes', 'valor_bruto', 'valor_liquido', 'lucro')
    filter_horizontal = ('despesas_mensais',) # Facilita selecionar várias despesas
    list_filter = ('mes',)

