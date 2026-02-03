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
