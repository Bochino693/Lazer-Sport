"""O RH no /system/ (admin do Django), para emergência -- quase tudo só leitura.

A tela de verdade é a do painel (interno., menu Pessoas). Aqui:
  * marcações de ponto, trilha de auditoria e termos: SÓ LEITURA, sem
    incluir, alterar nem apagar (a marcação nem o banco deixa);
  * documentos: sem o campo do arquivo -- ele não tem endereço, e abrir é
    pela ficha, que confere a permissão e anota quem abriu.
"""

from django.contrib import admin

from .models import (
    AjustePonto,
    Colaborador,
    DocumentoColaborador,
    MarcacaoPonto,
    RegistroRH,
    Tarefa,
    TermoExclusividade,
)


class SoLeitura(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ("nome", "cargo", "setor", "vinculo", "situacao", "data_admissao")
    list_filter = ("situacao", "setor", "vinculo")
    search_fields = ("nome", "cpf", "cargo")
    raw_id_fields = ("usuario", "colaborador_producao", "criado_por")

    def has_delete_permission(self, request, obj=None):
        # Ficha com ponto não se apaga (PROTECT); desligue pela situação.
        return False


@admin.register(DocumentoColaborador)
class DocumentoAdmin(SoLeitura):
    list_display = ("colaborador", "tipo", "descricao", "validade", "enviado_em")
    list_filter = ("tipo",)
    search_fields = ("colaborador__nome",)
    exclude = ("arquivo",)


@admin.register(MarcacaoPonto)
class MarcacaoAdmin(SoLeitura):
    list_display = ("colaborador", "nsr", "tipo", "momento", "ip")
    list_filter = ("tipo", "data")
    search_fields = ("colaborador__nome", "hash")


@admin.register(AjustePonto)
class AjusteAdmin(SoLeitura):
    list_display = ("colaborador", "tipo", "data", "situacao", "solicitado_em", "decidido_por")
    list_filter = ("situacao", "tipo")


@admin.register(Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "colaborador", "situacao", "prazo", "etapa", "origem_rotulo")
    list_filter = ("situacao", "prioridade", "setor")
    search_fields = ("titulo", "origem_rotulo")
    raw_id_fields = ("colaborador", "criada_por")


@admin.register(RegistroRH)
class RegistroAdmin(SoLeitura):
    list_display = ("momento", "usuario_nome", "acao", "colaborador", "descricao", "ip")
    list_filter = ("acao",)
    search_fields = ("usuario_nome", "descricao")


@admin.register(TermoExclusividade)
class TermoAdmin(SoLeitura):
    list_display = ("colaborador", "versao", "situacao", "gerado_em", "assinado_em", "canal")
    list_filter = ("situacao", "versao")
    exclude = ("assinatura_png",)
