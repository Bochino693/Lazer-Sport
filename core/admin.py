from django.contrib import admin
from .models import (
    CategoriasBrinquedos,
    TagsBrinquedos,
    Estabelecimentos,
    Brinquedos,
    ImagemBrinquedo,
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
    PecasReposicao,
    ImagemPeca,
    CategoriaPeca,
    Frete
)
from django.utils.html import format_html
from .models import ImagensSite
from django import forms
from django.core.exceptions import ValidationError



admin.site.site_header = "Painel Lazer Sport"
admin.site.site_title = "Lazer Sport Admin"
admin.site.index_title = "Bem-vindo ao Painel"


from django.contrib import admin
from .models import ItemCarrinho
from django.contrib.contenttypes.admin import GenericTabularInline

# Inline para exibir itens dentro do carrinho
class ItemCarrinhoInline(GenericTabularInline):
    model = ItemCarrinho
    extra = 0
    readonly_fields = ('preco_unitario', 'subtotal')
    fields = ('item', 'quantidade', 'preco_unitario', 'subtotal')
    can_delete = True
    show_change_link = True

# Admin principal para ItemCarrinho (opcional se quiser editar fora do inline)
@admin.register(ItemCarrinho)
class ItemCarrinhoAdmin(admin.ModelAdmin):
    list_display = ('id', 'carrinho', 'item', 'quantidade', 'preco_unitario', 'subtotal')
    list_filter = ('carrinho',)
    search_fields = ('carrinho__id', 'item__id')
    readonly_fields = ('preco_unitario', 'subtotal')

# ⭐ INLINE DAS IMAGENS
class ImagemPecaInline(admin.TabularInline):
    model = ImagemPeca
    extra = 0
    max_num = 8
    min_num = 0
    fields = ("ordem", "posicao", "imagem", "miniatura")
    readonly_fields = ("miniatura",)
    ordering = ("ordem", "id")
    show_change_link = True
    verbose_name = "Imagem da peça"
    verbose_name_plural = "Imagens da peça"

    @admin.display(description="Prévia")
    def miniatura(self, obj):
        if not obj or not obj.pk or not obj.imagem:
            return "Nova foto"
        return format_html(
            '<img src="{}" alt="" style="width:72px;height:54px;'
            'object-fit:contain;border-radius:8px;background:#eef4fb;" />',
            obj.imagem.url,
        )

    # 🔒 segurança extra no admin
    def clean(self):
        super().clean()
        total = len([
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False)
        ])
        if total > 8:
            raise ValidationError("Máximo de 8 imagens por peça.")


class GaleriaAdminBase(admin.ModelAdmin):
    """Editor individual que protege a posição já ocupada pela foto."""

    list_per_page = 40
    readonly_fields = ("preview_grande", "criacao", "atualizado")

    def get_readonly_fields(self, request, obj=None):
        campos = list(super().get_readonly_fields(request, obj))
        # Trocar o arquivo não deve mover acidentalmente a foto 1, 2, 3 etc.
        # A reordenação continua disponível no inline da galeria completa.
        if obj and obj.pk:
            campos.append("ordem")
        return tuple(campos)

    @admin.display(description="Foto")
    def miniatura(self, obj):
        if not obj or not obj.imagem:
            return "Sem imagem"
        return format_html(
            '<img src="{}" alt="" style="width:86px;height:64px;'
            'object-fit:contain;border-radius:10px;background:#eef4fb;" />',
            obj.imagem.url,
        )

    @admin.display(description="Pré-visualização")
    def preview_grande(self, obj):
        if not obj or not obj.pk or not obj.imagem:
            return "A prévia aparecerá depois que a imagem for salva."
        return format_html(
            '<img src="{}" alt="" style="max-width:420px;max-height:300px;'
            'object-fit:contain;border-radius:14px;background:#eef4fb;'
            'padding:10px;" />',
            obj.imagem.url,
        )


@admin.register(ImagemPeca)
class ImagemPecaAdmin(GaleriaAdminBase):
    list_display = (
        "miniatura",
        "peca_reposicao",
        "ordem",
        "posicao",
        "ativo",
        "atualizado",
    )
    list_display_links = ("miniatura", "peca_reposicao")
    list_filter = ("ativo", "posicao")
    search_fields = ("peca_reposicao__nome",)
    ordering = ("peca_reposicao__nome", "ordem", "id")
    list_select_related = ("peca_reposicao",)
    fields = (
        "peca_reposicao",
        "ordem",
        "posicao",
        "imagem",
        "preview_grande",
        "ativo",
        "criacao",
        "atualizado",
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "ordem" in form.base_fields:
            form.base_fields["ordem"].help_text = (
                "Defina o espaço da nova foto. Depois de salvar, a posição "
                "fica protegida neste editor individual. Para reorganizar a "
                "galeria, abra a peça e use a lista completa de imagens."
            )
        return form



# ===============================
# ⭐ CATEGORIA DE PEÇA
# ===============================
@admin.register(CategoriaPeca)
class CategoriaPecaAdmin(admin.ModelAdmin):
    list_display = ("id", "nome_categoria_peca")
    search_fields = ("nome_categoria_peca",)
    ordering = ("nome_categoria_peca",)


@admin.register(PecasReposicao)
class PecasReposicaoAdmin(admin.ModelAdmin):
    list_display = (
        "ativo",
        "id",
        "nome",
        "preco_venda",
        "preco_fornecedor",
        "mostrar_categorias",
    )

    list_display_links = ("id", "nome")

    # ⭐ permite marcar/desmarcar ativo direto na lista
    list_editable = ("ativo",)

    search_fields = ("nome", "descricao_peca")

    list_filter = (
        "ativo",          # ⭐ filtro por ativo/inativo
        "categoria_peca",
    )

    filter_horizontal = ("categoria_peca",)

    inlines = [ImagemPecaInline]

    fieldsets = (
        ("Status", {
            "fields": ("ativo",)  # ⭐ campo agora aparece no formulário
        }),

        ("Informações da Peça", {
            "fields": (
                "nome",
                "descricao_peca",
                "categoria_peca",
            )
        }),

        ("Valores", {
            "fields": (
                "preco_venda",
                "preco_fornecedor",
            )
        }),
    )

    # ⭐ mostra categorias na lista
    def mostrar_categorias(self, obj):
        return ", ".join([c.nome_categoria_peca for c in obj.categoria_peca.all()])

    mostrar_categorias.short_description = "Categorias"


@admin.register(Frete)
class FreteAdmin(admin.ModelAdmin):
    # Colunas que aparecerão na listagem
    list_display = (
        'get_carrinho_id',
        'get_cliente',
        'cidade',
        'bairro',
        'valor',
        'distancia_km',
        'tempo_estimado_min'
    )

    # Filtros laterais para facilitar a navegação
    list_filter = ('estado', 'cidade', 'bairro')

    # Campos de busca (CEP, Rua, Bairro e Nome do Usuário do Carrinho)
    search_fields = (
        'cep',
        'rua',
        'bairro',
        'carrinho__cliente__user__username',
        'carrinho__id'
    )

    # Organização dos campos dentro do formulário de edição
    fieldsets = (
        ('Vínculo', {
            'fields': ('carrinho',)
        }),
        ('Endereço Completo', {
            'fields': (('cep', 'numero'), 'rua', 'bairro', ('cidade', 'estado'))
        }),
        ('Logística e Valores', {
            'fields': (('valor', 'distancia_km', 'tempo_estimado_min'),)
        }),
    )

    # Métodos para exibir informações do Carrinho na listagem
    @admin.display(ordering='carrinho__id', description='Carrinho #')
    def get_carrinho_id(self, obj):
        return f"#{obj.carrinho.id}" if obj.carrinho else "-"

    @admin.display(description='Cliente')
    def get_cliente(self, obj):
        if obj.carrinho and obj.carrinho.cliente:
            return obj.carrinho.cliente.user.username
        return "Sem cliente"


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


class ImagemBrinquedoInline(admin.TabularInline):
    model = ImagemBrinquedo
    extra = 0
    max_num = 8
    fields = ("ordem", "imagem", "texto_alternativo", "miniatura")
    readonly_fields = ("miniatura",)
    ordering = ("ordem", "id")
    show_change_link = True
    verbose_name = "Foto do brinquedo"
    verbose_name_plural = "Galeria do brinquedo"

    @admin.display(description="Prévia")
    def miniatura(self, obj):
        if not obj or not obj.pk or not obj.imagem:
            return "Nova foto"
        return format_html(
            '<img src="{}" alt="" style="width:72px;height:54px;'
            'object-fit:contain;border-radius:8px;background:#eef4fb;" />',
            obj.imagem.url,
        )


@admin.register(ImagemBrinquedo)
class ImagemBrinquedoAdmin(GaleriaAdminBase):
    list_display = (
        "miniatura",
        "brinquedo",
        "ordem",
        "descricao_curta",
        "ativo",
        "atualizado",
    )
    list_display_links = ("miniatura", "brinquedo")
    list_filter = ("ativo",)
    search_fields = ("brinquedo__nome_brinquedo", "texto_alternativo")
    ordering = ("brinquedo__nome_brinquedo", "ordem", "id")
    list_select_related = ("brinquedo",)
    fields = (
        "brinquedo",
        "ordem",
        "imagem",
        "preview_grande",
        "texto_alternativo",
        "ativo",
        "criacao",
        "atualizado",
    )

    @admin.display(description="Descrição")
    def descricao_curta(self, obj):
        texto = (obj.texto_alternativo or "Sem descrição").strip()
        return texto if len(texto) <= 55 else f"{texto[:52]}..."

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "ordem" in form.base_fields:
            form.base_fields["ordem"].help_text = (
                "Defina o espaço da nova foto. Depois de salvar, a posição "
                "fica protegida neste editor individual. Para reorganizar a "
                "galeria, abra o brinquedo e use a lista completa de fotos."
            )
        return form

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # A posição 1 também alimenta telas antigas. Alterar as posições 2 a 8
        # nunca substitui a foto principal do brinquedo.
        if obj.ordem == 1 and obj.imagem:
            Brinquedos.objects.filter(pk=obj.brinquedo_id).update(
                imagem_brinquedo=obj.imagem.name
            )


@admin.register(Brinquedos)
class BrinquedosAdmin(admin.ModelAdmin):
    list_display = ('nome_brinquedo', 'avaliacao', 'voltz', 'exibir_na_loja', 'ativo', 'criacao')
    search_fields = ('nome_brinquedo', 'descricao', 'estabelecimento__nome_estabelecimento')
    list_filter = ('ativo', 'exibir_na_loja', 'estabelecimentos', 'categorias_brinquedos', 'tags')
    readonly_fields = ('criacao', 'atualizado')
    filter_horizontal = ('categorias_brinquedos', 'tags', 'estabelecimentos')
    ordering = ('-criacao',)
    inlines = [ImagemBrinquedoInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        brinquedo = form.instance
        if "imagem_brinquedo" in form.changed_data:
            brinquedo.sincronizar_imagem_legada_com_galeria()
            return

        principal = brinquedo.imagens_brinquedo.first()
        if (
            principal
            and principal.imagem
            and brinquedo.imagem_brinquedo.name != principal.imagem.name
        ):
            Brinquedos.objects.filter(pk=brinquedo.pk).update(
                imagem_brinquedo=principal.imagem.name
            )


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
    list_display = ('codigo', 'desconto_percentual', 'todos_usuarios', 'exibir_na_vitrine', 'ativo')
    list_filter = ('todos_usuarios', 'exibir_na_vitrine', 'ativo')
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


# ============================================================
# CURTIDAS E LISTA DE DESEJOS
# ============================================================

from .models import Favorito


@admin.register(Favorito)
class FavoritoAdmin(admin.ModelAdmin):
    """Só leitura: quem marca é o cliente, no site ou no aplicativo.

    Editar aqui furaria a regra de uma marcação por conta/aparelho, então
    a tela serve para conferir e, no máximo, apagar registro de teste.
    """

    list_display = (
        "tipo",
        "produto_marcado",
        "quem_marcou",
        "origem",
        "criacao",
    )
    list_filter = ("tipo", "origem", "criacao")
    search_fields = (
        "brinquedo__nome_brinquedo",
        "peca__nome",
        "usuario__username",
        "usuario__first_name",
        "usuario__email",
        "dispositivo",
    )
    autocomplete_fields = ("brinquedo", "peca", "usuario")
    date_hierarchy = "criacao"
    list_select_related = ("brinquedo", "peca", "usuario")

    @admin.display(description="Produto", ordering="brinquedo__nome_brinquedo")
    def produto_marcado(self, obj):
        return obj.nome_produto

    @admin.display(description="Quem marcou")
    def quem_marcou(self, obj):
        if obj.usuario:
            return obj.usuario.get_full_name() or obj.usuario.username
        return f"Visitante · {obj.dispositivo[:8]}…"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ============================================================
# PONTOS E LOJA DE CUPONS
# ============================================================

from .models import CarteiraPontos, PontoGanho, RecompensaCupom, ResgateCupom


@admin.register(RecompensaCupom)
class RecompensaCupomAdmin(admin.ModelAdmin):
    """A vitrine da loja de pontos do aplicativo.

    É a única tela editável desta parte: preço em pontos, desconto e
    estoque são decisão comercial. O resto (extrato, carteira, resgates)
    é histórico e não se edita.
    """

    list_display = (
        "nome",
        "custo_pontos",
        "desconto_percentual",
        "validade_dias",
        "estoque",
        "ativo",
        "exibir_na_vitrine_site",
        "ordem",
    )
    list_editable = ("custo_pontos", "estoque", "ativo", "exibir_na_vitrine_site", "ordem")
    list_filter = ("ativo", "exibir_na_vitrine_site")
    search_fields = ("nome", "descricao")
    ordering = ("ordem", "custo_pontos")

    fieldsets = (
        ("O que o cliente vê", {
            "fields": ("nome", "descricao", "ordem", "ativo", "exibir_na_vitrine_site"),
        }),
        ("Preço e prêmio", {
            "description": (
                "O custo é em pontos. Curtida vale 5; a meta de 5 itens "
                "na lista de desejos vale 30."
            ),
            "fields": ("custo_pontos", "desconto_percentual", "validade_dias"),
        }),
        ("Limite", {
            "description": "Estoque vazio significa ilimitado.",
            "fields": ("estoque",),
        }),
    )


@admin.register(ResgateCupom)
class ResgateCupomAdmin(admin.ModelAdmin):
    """Histórico: quem trocou pontos por qual cupom."""

    list_display = (
        "codigo_do_cupom",
        "usuario",
        "recompensa",
        "pontos_gastos",
        "criacao",
        "expira_em",
    )
    list_filter = ("recompensa", "criacao")
    search_fields = (
        "cupom__codigo",
        "usuario__username",
        "usuario__first_name",
        "usuario__email",
    )
    date_hierarchy = "criacao"
    list_select_related = ("cupom", "recompensa", "usuario")

    @admin.display(description="Cupom", ordering="cupom__codigo")
    def codigo_do_cupom(self, obj):
        return obj.cupom.codigo

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PontoGanho)
class PontoGanhoAdmin(admin.ModelAdmin):
    """Extrato. Só leitura: o saldo é a soma daqui, e editar à mão
    faria a carteira e o extrato contarem histórias diferentes."""

    list_display = ("usuario", "pontos", "origem", "descricao", "criacao")
    list_filter = ("origem", "criacao")
    search_fields = ("usuario__username", "usuario__email", "descricao")
    date_hierarchy = "criacao"
    list_select_related = ("usuario",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CarteiraPontos)
class CarteiraPontosAdmin(admin.ModelAdmin):
    list_display = ("usuario", "saldo", "total_ganho", "atualizado")
    search_fields = ("usuario__username", "usuario__email")
    list_select_related = ("usuario",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
