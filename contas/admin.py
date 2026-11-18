"""O /system/ pelas regras de conta.

  * o login do /system/ passa pelo freio de tentativas (FormularioLoginAdmin);
  * o cadastro de usuários confere o e-mail como o painel confere
    (UsuarioAdminForm) e grava os endereços do allauth junto;
  * as ocorrências de segurança aparecem só para leitura -- quem resolve é
    a tela "Segurança das contas" do painel, que registra quem e quando.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .emails import sincronizar_enderecos
from .forms import FormularioLoginAdmin, NovoUsuarioAdminForm, UsuarioAdminForm
from .models import OcorrenciaSeguranca

admin.site.login_form = FormularioLoginAdmin

User = get_user_model()


class ContaAdmin(UserAdmin):
    form = UsuarioAdminForm
    add_form = NovoUsuarioAdminForm
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "password1", "password2")}),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change or "email" in form.changed_data:
            sincronizar_enderecos(obj)


if admin.site.is_registered(User):
    admin.site.unregister(User)
admin.site.register(User, ContaAdmin)


@admin.register(OcorrenciaSeguranca)
class OcorrenciaSegurancaAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "tipo", "situacao", "username", "email_original", "login_tentado", "ip", "origem")
    list_filter = ("tipo", "situacao", "origem")
    search_fields = ("username", "email_original", "login_tentado", "ip")
    readonly_fields = [campo.name for campo in OcorrenciaSeguranca._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
