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
    Cupom
)
from django.utils.html import format_html
from .models import ImagensSite


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
    list_display = ('nome_estabelecimento', 'ativo', 'criacao')
    search_fields = ('nome_estabelecimento',)
    list_filter = ('ativo',)
    ordering = ('nome_estabelecimento',)


@admin.register(Brinquedos)
class BrinquedosAdmin(admin.ModelAdmin):
    list_display = ('nome_brinquedo', 'avaliacao', 'voltz', 'ativo', 'criacao')
    search_fields = ('nome_brinquedo', 'descricao')
    list_filter = ('ativo', 'categorias_brinquedos', 'tags')
    readonly_fields = ('criacao', 'atualizado')
    filter_horizontal = ('categorias_brinquedos', 'tags')
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
