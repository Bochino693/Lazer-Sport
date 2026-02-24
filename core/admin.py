from django.contrib import admin
from .models import (
    Clientes,
    CategoriasBrinquedos,
    TagsBrinquedos,
    Estabelecimentos,
    Brinquedos,
    Projetos,
    ImagemEvento,
    Eventos,
    ImagemProjetoBrinquedo,
    BrinquedosProjeto,
    Combos,
    Promocoes,
    Cupom,
    Manutencao,
    ManutencaoImagem,
    Pedido,
    ItemPedido,
    EnderecoEmpresa,
    BrinquedoClick,
    CategoriaClick,
    PromocaoClick,
    ComboClick,
    PecasReposicao
)
from django.utils.html import format_html
from .models import ImagensSite
from django import forms
from .models import EnderecoEntrega


admin.site.site_header = "Painel Lazer Sport"
admin.site.site_title = "Lazer Sport Admin"
admin.site.index_title = "Bem-vindo ao Painel"

@admin.register(PecasReposicao)
class PecasReposicaoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nome",
        "preco_venda",
        "preco_fornecedor",
        "descricao_peca",
    )
    list_display_links = ("id", "nome")
    search_fields = ("nome", "descricao_peca")
    list_filter = ("preco_venda", "preco_fornecedor")
    readonly_fields = ()

    fieldsets = (
        ("Informações da Peça", {
            "fields": (
                "nome",
                "descricao_peca",
                "imagem_peca",
            )
        }),
        ("Valores", {
            "fields": (
                "preco_venda",
                "preco_fornecedor",
            )
        }),
    )

@admin.register(BrinquedoClick)
class BrinquedoClickAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "brinquedo_clicado",
        "quantidade_click",
        "criacao"
    )
    search_fields = (
        "brinquedo_clicado__nome_brinquedo",
    )
    list_filter = (
        "brinquedo_clicado", "criacao"
    )
    ordering = ("-quantidade_click",)


@admin.register(ComboClick)
class ComboClickAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "descricao_combo",
        "combo_clicado",
        "valor_combo",
        "quantidade_click",
        "criacao"
    )
    search_fields = (
        "descricao_combo",
    )
    list_filter = (
        "combo_clicado", "criacao"
    )
    ordering = ("-quantidade_click",)


@admin.register(PromocaoClick)
class PromocaoClickAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "descricao_promocao",
        "promocao",
        "preco_promocao",
        "quantidade_click",
        "criacao"
    )
    search_fields = (
        "descricao_promocao",
    )
    list_filter = (
        "promocao", "criacao"
    )
    ordering = ("-quantidade_click",)


@admin.register(CategoriaClick)
class CategoriaClickAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nome_categoria",
        "categoria",
        "quantidade_click",
        "criacao"
    )
    search_fields = (
        "nome_categoria",
    )
    list_filter = (
        "categoria", "criacao"
    )
    ordering = ("-quantidade_click",)


@admin.register(ImagensSite)
class ImagensSiteAdmin(admin.ModelAdmin):
    list_display = ("id", "preview_imagem")
    list_display_links = ("id", "preview_imagem")

    def preview_imagem(self, obj):
        if obj.imagem:
            return format_html(
                '<img src="{}" style="height:60px; width:auto; border-radius:6px;" />',
                obj.imagem.url
            )
        return "—"

    preview_imagem.short_description = "Imagem"


# ========= MODELOS PRINCIPAIS =========
@admin.register(Clientes)
class ClientesAdmin(admin.ModelAdmin):
    list_display = ('id', 'logo_cliente', 'ativo', 'criacao', 'atualizado')
    list_filter = ('ativo',)
    search_fields = ('id',)
    readonly_fields = ('criacao', 'atualizado')
    ordering = ('-criacao',)


@admin.register(CategoriasBrinquedos)
class CategoriasBrinquedosAdmin(admin.ModelAdmin):
    list_display = ('nome_categoria', 'ativo', 'criacao')
    search_fields = ('nome_categoria',)
    list_filter = ('ativo',)
    ordering = ('nome_categoria',)


@admin.register(TagsBrinquedos)
class TagsBrinquedosAdmin(admin.ModelAdmin):
    list_display = ('nome_tags', 'ativo', 'criacao')
    search_fields = ('nome_tags',)
    ordering = ('nome_tags',)


@admin.register(Estabelecimentos)
class EstabelecimentosAdmin(admin.ModelAdmin):
    list_display = ('nome_estabelecimento', 'total_brinquedos', 'ativo', 'criacao')
    search_fields = ('nome_estabelecimento',)
    list_filter = ('ativo',)
    ordering = ('nome_estabelecimento',)

    def total_brinquedos(self, obj):
        return obj.brinquedos.count()

    total_brinquedos.short_description = "Brinquedos"


@admin.register(Brinquedos)
class BrinquedosAdmin(admin.ModelAdmin):
    list_display = ('nome_brinquedo', 'avaliacao', 'voltz', 'ativo', 'criacao')
    search_fields = ('nome_brinquedo', 'descricao', 'estabelecimento__nome_estabelecimento')
    list_filter = ('ativo', 'estabelecimentos', 'categorias_brinquedos', 'tags')
    readonly_fields = ('criacao', 'atualizado')
    filter_horizontal = ('categorias_brinquedos', 'tags', 'estabelecimentos')
    ordering = ('-criacao',)


# ============================================
# INLINE PROJETOS
# ============================================
class ImagemProjetoBrinquedoInline(admin.TabularInline):
    model = ImagemProjetoBrinquedo
    extra = 1
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj.imagem:
            return f'<img src="{obj.imagem.url}" width="120" />'
        return "Sem imagem"

    preview.allow_tags = True
    preview.short_description = "Prévia"


@admin.register(BrinquedosProjeto)
class BrinquedosProjetoAdmin(admin.ModelAdmin):
    list_display = ("nome_brinquedo_projeto",)
    inlines = [ImagemProjetoBrinquedoInline]


@admin.register(Projetos)
class ProjetosAdmin(admin.ModelAdmin):
    list_display = ("titulo", "brinquedo_projetado")
    search_fields = ("titulo", "descricao")
    # OneToOneField usa dropdown padrão


class ImagemEventoInline(admin.TabularInline):
    model = ImagemEvento
    extra = 1
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj.imagem:
            return f'<img src="{obj.imagem.url}" width="120" />'
        return "Sem imagem"

    preview.allow_tags = True
    preview.short_description = "Prévia"


@admin.register(Eventos)
class EventosAdmin(admin.ModelAdmin):
    list_display = ("titulo", "total_brinquedos")
    search_fields = ("titulo", "descricao")
    filter_horizontal = ("brinquedos",)
    inlines = [ImagemEventoInline]

    def total_brinquedos(self, obj):
        return obj.brinquedos.count()


@admin.register(ImagemEvento)
class ImagemEventoAdmin(admin.ModelAdmin):
    list_display = ("evento", "preview")
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj.imagem:
            return f'<img src="{obj.imagem.url}" width="120" />'
        return "Sem imagem"


@admin.register(Combos)
class CombosAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'valor_combo')
    search_fields = ('descricao',)
    filter_horizontal = ('brinquedos',)


@admin.register(Promocoes)
class PromocoesAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'brinquedos', 'preco_promocao')
    search_fields = ('descricao', 'brinquedos__nome')
    list_filter = ('brinquedos',)


@admin.register(Cupom)
class CupomAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'desconto_percentual')
    search_fields = ('codigo',)


class ManutencaoImagemInline(admin.TabularInline):
    model = ManutencaoImagem
    extra = 1


@admin.register(Manutencao)
class ManutencaoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'brinquedo',
        'usuario',
        'telefone_contato',
        'cidade',
        'estado',
        'status',
        'criado_em',
    )

    list_filter = (
        'status',
        'estado',
        'criado_em',
    )

    search_fields = (
        'brinquedo__nome_brinquedo',  # ajuste comum
        'usuario__user__username',
        'usuario__nome_completo',
        'telefone_contato',
        'cep',
    )

    readonly_fields = ('criado_em',)

    fieldsets = (
        ('Informações da Manutenção', {
            'fields': (
                'brinquedo',
                'descricao',
                'status',
            )
        }),
        ('Cliente', {
            'fields': (
                'usuario',
                'telefone_contato',
            )
        }),
        ('Endereço', {
            'fields': (
                'cep',
                'endereco',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'estado',
            )
        }),
        ('Datas', {
            'fields': (
                'criado_em',
            )
        }),
    )

    inlines = [ManutencaoImagemInline]


@admin.register(ManutencaoImagem)
class ManutencaoImagemAdmin(admin.ModelAdmin):
    list_display = ('id', 'manutencao')


from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import Carrinho, ItemCarrinho


# ===============================
# INLINE DOS ITENS DO CARRINHO
# ===============================
class ItemCarrinhoInline(GenericTabularInline):
    model = ItemCarrinho
    extra = 0
    readonly_fields = (
        'item',
        'preco_unitario_admin',
        'subtotal_admin',
    )
    fields = (
        'item',
        'quantidade',
        'preco_unitario_admin',
        'subtotal_admin',
    )

    def preco_unitario_admin(self, obj):
        return f"R$ {obj.preco_unitario:.2f}"

    preco_unitario_admin.short_description = "Preço Unitário"

    def subtotal_admin(self, obj):
        return f"R$ {obj.subtotal:.2f}"

    subtotal_admin.short_description = "Subtotal"


# ===============================
# ADMIN DO CARRINHO
# ===============================
@admin.register(Carrinho)
class CarrinhoAdmin(admin.ModelAdmin):
    list_display = (
        'cliente',
        'total_bruto_admin',
        'desconto_admin',
        'total_liquido_admin',
        'cupom',

    )

    list_filter = ('cupom',)
    search_fields = (
        'cliente__user__username',
        'cliente__user__email',
    )

    readonly_fields = (
        'total_bruto_admin',
        'desconto_admin',
        'total_liquido_admin',
    )

    inlines = [ItemCarrinhoInline]

    def total_bruto_admin(self, obj):
        return f"R$ {obj.total_bruto:.2f}"

    total_bruto_admin.short_description = "Total Bruto"

    def desconto_admin(self, obj):
        return f"- R$ {obj.valor_desconto:.2f}"

    desconto_admin.short_description = "Desconto"

    def total_liquido_admin(self, obj):
        return f"R$ {obj.total_liquido:.2f}"

    total_liquido_admin.short_description = "Total Líquido"

    def has_change_permission(self, request, obj=None):
        if obj and obj.status == 'finalizado':
            return False
        return super().has_change_permission(request, obj)


# ===========================
# ADMIN DO ITEM DO PEDIDO
# ===========================
from django.contrib import admin


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 1  # Começa com uma linha vazia para facilitar a criação
    readonly_fields = ()
    can_delete = True


# ===========================
# ADMIN DO PEDIDO
# ===========================
@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'cliente_usuario', 'status', 'forma_pagamento',
        'total_bruto', 'valor_desconto', 'total_liquido', 'cupom_codigo', 'criacao'
    )
    list_filter = ('status', 'forma_pagamento', 'criacao')
    search_fields = ('id', 'cliente__user__username', 'cupom_codigo')
    readonly_fields = ('total_bruto', 'valor_desconto', 'total_liquido')  # snapshot financeiro
    inlines = [ItemPedidoInline]
    ordering = ('-criacao',)

    def cliente_usuario(self, obj):
        return obj.cliente.user.username if obj.cliente else "Guest"

    cliente_usuario.short_description = "Cliente"


# ===========================
# ADMIN DO ITEM DO PEDIDO (opcional separado)
# ===========================
@admin.register(ItemPedido)
class ItemPedidoAdmin(admin.ModelAdmin):
    list_display = ('nome_item', 'tipo_item', 'pedido', 'preco_unitario', 'quantidade', 'subtotal')
    list_filter = ('tipo_item',)
    search_fields = ('nome_item', 'pedido__id')
    readonly_fields = ('nome_item', 'tipo_item', 'preco_unitario', 'quantidade', 'subtotal')


class EnderecoEntregaForm(forms.ModelForm):
    class Meta:
        model = EnderecoEntrega
        fields = [
            'cep',
            'rua',
            'numero',
            'complemento',
            'bairro',
            'cidade',
            'estado',
        ]


@admin.register(EnderecoEmpresa)
class EnderecoEmpresaAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'cidade',
        'estado',
        'cep',
        'telefone',
        'latitude',
        'longitude',
    )

    list_filter = (
        'estado',
        'cidade',
    )

    search_fields = (
        'nome',
        'cep',
        'cidade',
        'estado',
        'rua',
    )

    fieldsets = (
        ('Identificação', {
            'fields': ('nome', 'telefone')
        }),
        ('Endereço', {
            'fields': (
                'cep',
                'rua',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'estado',
            )
        }),
        ('Geolocalização', {
            'description': 'Use valores como: -23.454013, -46.662676',
            'fields': ('latitude', 'longitude')
        }),
    )

    ordering = ('nome',)


from .models import EnderecoEntrega, Pedido

@admin.register(EnderecoEntrega)
class EnderecoEntregaAdmin(admin.ModelAdmin):
    list_display = (
        'pedido',
        'cep',
        'rua',
        'numero',
        'bairro',
        'cidade',
        'estado',
        'telefone',
        'latitude',
        'longitude',
    )
    list_filter = ('cidade', 'estado')
    search_fields = ('pedido__id', 'cep', 'rua', 'bairro', 'cidade', 'estado', 'telefone')
    #readonly_fields = ('latitude', 'longitude')  # latitude e longitude não devem ser editáveis manualmente
    fieldsets = (
        (None, {
            'fields': (
                'pedido',
                'telefone',
                'cep',
                'rua',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'estado',
            )
        }),
        ('Coordenadas (geocodificação)', {
            'fields': ('latitude', 'longitude'),
        }),
    )