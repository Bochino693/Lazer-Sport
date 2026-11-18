"""Os formulários de fora da casa que precisavam das regras de conta.

  * `AdicionarEmailForm` -- o "Meus e-mails" do allauth (/accounts/email/).
    O original não chama `validate_unique_email` e, com a proteção contra
    enumeração ligada, ACRESCENTA a uma conta o e-mail que já é de outra
    (só manda a confirmação). Foi uma das portas do e-mail repetido.
  * `FormularioLoginAdmin` -- o login do /system/ pelo freio de tentativas,
    com a mensagem de "pausado até HH:MM" em vez do "usuário ou senha
    incorretos" de sempre.
  * `UsuarioAdminForm` / `NovoUsuarioAdminForm` -- o e-mail e a senha das
    contas editadas no /system/ pelas mesmas regras do painel.
"""

from __future__ import annotations

from allauth.account.forms import AddEmailForm
from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from . import emails as regras
from . import freio


class AdicionarEmailForm(AddEmailForm):
    def clean_email(self):
        valor = super().clean_email()
        return regras.validar_email_de_conta(valor, usuario=self.user)


class FormularioLoginAdmin(AdminAuthenticationForm):
    def clean(self):
        login = self.cleaned_data.get("username")
        senha = self.cleaned_data.get("password")
        if login is not None and senha:
            tentativa = freio.autenticar(self.request, login, senha, origem="admin")
            if tentativa.bloqueada:
                raise forms.ValidationError(tentativa.mensagem, code="bloqueado")
            if tentativa.usuario is None:
                raise self.get_invalid_login_error()
            self.user_cache = tentativa.usuario
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class _EmailDaContaMixin:
    def clean_email(self):
        email = self.cleaned_data.get("email")
        conta = self.instance if getattr(self.instance, "pk", None) else None
        return regras.validar_email_de_conta(email, usuario=conta, pela_equipe=True)


class UsuarioAdminForm(_EmailDaContaMixin, UserChangeForm):
    pass


class NovoUsuarioAdminForm(_EmailDaContaMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")
