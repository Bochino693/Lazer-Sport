from django.contrib import admin
from django.utils.html import format_html
from .models import Colaborador, Material, TipoMaterial, Gerente


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


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "atualizado")
    list_filter = ("ativo",)
    search_fields = ("nome",)


from .models import (
    AvaliacaoBlocoOrcamento, AvaliacaoSetor,
    Cliente, EnderecoCliente, Setores, EstoqueMaterial,
    CentralPedidos, CentralVendas, ComprasMensais, ItensCompra,
    CategoriaDespesa, DespesasMensais, FinanceiroMensal,
    ExecucaoEtapaProducao, Fornecedor, GuiaEtapaProducao,
    HistoricoProducao, ImagemGuiaProducao, MovimentoEstoque,
    Orcamento, OrdemProducao, ProdutoInterno,
)

# Inline para endereços dentro do Cliente
class EnderecoClienteInline(admin.StackedInline):
    model = EnderecoCliente
    extra = 1
    fields = (
        ("cep", "numero"),
        ("endereco", "complemento"),
        ("bairro", "cidade", "estado"),
        "pais",
        ("latitude", "longitude", "precisao"),
    )


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    """O cadastro único: painel e mapa do site na mesma ficha."""

    list_display = (
        "nome_cliente", "tipo", "telefone", "email",
        "parceiro", "publicar_no_mapa", "alfinete", "ativo", "criacao",
    )
    list_filter = ("tipo", "ativo", "publicar_no_mapa")
    search_fields = ("nome_cliente", "email", "telefone", "telefone_digitos", "documento")
    inlines = [EnderecoClienteInline]
    fieldsets = (
        (None, {
            "fields": ("nome_cliente", "tipo", "documento", "ativo"),
        }),
        ("Contato", {
            "fields": ("telefone", "email"),
        }),
        ("Vínculos", {
            "fields": ("parceiro", "estabelecimento"),
        }),
        ("No site", {
            "fields": ("publicar_no_mapa", "logo", "site_cliente"),
            "description": (
                "O alfinete do mapa sai do endereço do estabelecimento, logo "
                "abaixo. Sem coordenada, o cliente fica marcado para o mapa "
                "mas não é desenhado -- a lista mostra isso na coluna Alfinete."
            ),
        }),
        ("Observações", {
            "fields": ("observacoes",),
        }),
    )

    @admin.display(description="Alfinete")
    def alfinete(self, obj):
        """Diz, na lista, quais pontos são o endereço e quais são só a região.

        Sem esta coluna não havia como saber: um alfinete no centro da
        cidade e um alfinete na porta do cliente apareciam exatamente
        iguais no cadastro.
        """
        endereco = obj.endereco_principal
        if not endereco or not endereco.tem_local:
            return format_html('<span style="color:#b91c1c">sem ponto</span>')

        rotulos = {
            EnderecoCliente.Precisao.EXATO: ("#15803d", "no endereço"),
            EnderecoCliente.Precisao.MANUAL: ("#15803d", "à mão"),
            EnderecoCliente.Precisao.RUA: ("#a16207", "meio da rua"),
            EnderecoCliente.Precisao.BAIRRO: ("#b45309", "só o bairro"),
            EnderecoCliente.Precisao.CIDADE: ("#b91c1c", "só a cidade"),
        }
        cor, texto = rotulos.get(endereco.precisao, ("#6b7280", "não conferido"))
        return format_html('<span style="color:{}">{}</span>', cor, texto)

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


@admin.register(Orcamento)
class OrcamentoAdmin(admin.ModelAdmin):
    list_display = (
        "id", "cliente", "origem", "status", "responsavel", "criacao",
    )
    list_filter = ("origem", "status", "criacao")
    search_fields = (
        "nome_cliente", "cliente__nome_cliente", "contato",
        "responsavel__username", "responsavel__first_name",
    )
    autocomplete_fields = ("cliente", "responsavel")


@admin.register(AvaliacaoBlocoOrcamento)
class AvaliacaoBlocoOrcamentoAdmin(admin.ModelAdmin):
    list_display = (
        "orcamento", "bloco", "status", "avaliador", "avaliado_em",
    )
    list_filter = ("bloco", "status", "avaliado_em")
    search_fields = (
        "orcamento__nome_cliente", "orcamento__cliente__nome_cliente",
        "avaliador__username", "observacao",
    )
    autocomplete_fields = ("orcamento", "avaliador")


@admin.register(AvaliacaoSetor)
class AvaliacaoSetorAdmin(admin.ModelAdmin):
    list_display = ("setor", "periodo", "nota", "avaliador", "atualizado")
    list_filter = ("setor", "nota", "periodo")
    search_fields = ("observacao", "avaliador__username")
    autocomplete_fields = ("avaliador",)

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
    search_fields = ("produto__nome", "colaborador__nome", "observacoes")
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
