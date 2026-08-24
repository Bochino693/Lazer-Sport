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
    list_display = (
        'nome_material', 'codigo_interno', 'tipo_material', 'unidade', 'ativo',
    )
    list_filter = ('ativo', 'unidade', 'tipo_material')
    search_fields = ('nome_material', 'codigo_interno', 'descricao')
    ordering = ('nome_material',)


from .models import (
    Cliente, EnderecoCliente, Setores, EstoqueMaterial,
    CentralPedidos, CentralVendas, ComprasMensais, ItensCompra,
    CategoriaDespesa, DespesasMensais, FinanceiroMensal,
    ExecucaoEtapaProducao, Fornecedor, GuiaEtapaProducao,
    HistoricoProducao, ImagemGuiaProducao, MovimentoEstoque,
    OrdemProducao, ProdutoInterno,
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

@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'telefone', 'email', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'cnpj', 'email', 'telefone')


@admin.register(EstoqueMaterial)
class EstoqueMaterialAdmin(admin.ModelAdmin):
    list_display = (
        'material', 'descricao_local', 'fornecedor',
        'quantidade', 'estoque_minimo', 'preco_fornecedor',
    )
    list_filter = ('descricao_local', 'fornecedor', 'material__tipo_material')
    search_fields = (
        'material__nome_material', 'descricao_local', 'nota_fiscal',
    )
    autocomplete_fields = ('fornecedor',)


@admin.register(MovimentoEstoque)
class MovimentoEstoqueAdmin(admin.ModelAdmin):
    list_display = (
        'ocorrido_em', 'estoque', 'tipo', 'quantidade',
        'quantidade_resultante', 'valor_unitario', 'responsavel',
    )
    list_filter = ('tipo', 'ocorrido_em')
    search_fields = (
        'estoque__material__nome_material',
        'estoque__descricao_local',
        'documento',
        'motivo',
    )
    date_hierarchy = 'ocorrido_em'
    # A quantidade do estoque so muda por MovimentoEstoque.registrar();
    # editar o historico aqui deixaria saldo e rastro divergentes.
    readonly_fields = ('quantidade_resultante',)

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


class ImagemGuiaProducaoInline(admin.TabularInline):
    model = ImagemGuiaProducao
    extra = 0
    fields = ("ordem", "imagem", "legenda")


@admin.register(GuiaEtapaProducao)
class GuiaEtapaProducaoAdmin(admin.ModelAdmin):
    list_display = ("produto", "ordem", "titulo", "ativo", "atualizado")
    list_filter = ("ativo", "produto")
    search_fields = ("produto__nome", "titulo", "instrucoes")
    ordering = ("produto__nome", "ordem")
    inlines = (ImagemGuiaProducaoInline,)


@admin.register(OrdemProducao)
class OrdemProducaoAdmin(admin.ModelAdmin):
    list_display = ("id", "produto", "quantidade", "colaborador", "status", "prevista_para")
    list_filter = ("status", "prevista_para")
    search_fields = ("produto__nome", "colaborador__username", "observacoes")
    autocomplete_fields = ("colaborador", "responsavel")


@admin.register(ExecucaoEtapaProducao)
class ExecucaoEtapaProducaoAdmin(admin.ModelAdmin):
    list_display = ("ordem_producao", "guia_etapa", "status", "atualizado_por", "atualizado")
    list_filter = ("status",)
    readonly_fields = ("ordem_producao", "guia_etapa", "iniciado_em", "concluido_em", "atualizado_por")


@admin.register(HistoricoProducao)
class HistoricoProducaoAdmin(admin.ModelAdmin):
    list_display = ("ordem_producao", "evento", "usuario", "status_novo", "criacao")
    list_filter = ("evento", "criacao")
    readonly_fields = (
        "ordem_producao", "etapa", "usuario", "evento",
        "status_anterior", "status_novo", "observacao", "criacao", "atualizado",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
