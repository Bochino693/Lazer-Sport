"""Contas especiais da equipe e delegação de funções."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.generic import View

from .permissoes import (
    FUNCOES,
    NOMES_DOS_GRUPOS,
    atribuir_funcoes,
    nomes_das_funcoes,
)
from .utils import ErroDeFormulario, texto
from .views import RespostaJSONMixin, SuperusuarioInternoRequiredMixin


class UsuariosEquipeInnerView(
    RespostaJSONMixin,
    SuperusuarioInternoRequiredMixin,
    View,
):
    """Uma conta, várias funções; nenhuma subclasse de usuário."""

    rota_padrao = "usuarios_equipe"
    template_name = "usuarios_equipe.html"

    def get(self, request):
        busca = (request.GET.get("q") or "").strip()
        usuarios = (
            User.objects.filter(
                Q(is_superuser=True)
                | Q(groups__name__in=NOMES_DOS_GRUPOS)
                | Q(is_staff=True)
            )
            .prefetch_related("groups")
            .distinct()
            .order_by("-is_superuser", "first_name", "username")
        )
        if busca:
            usuarios = usuarios.filter(
                Q(username__icontains=busca)
                | Q(first_name__icontains=busca)
                | Q(last_name__icontains=busca)
                | Q(email__icontains=busca)
            )

        linhas = [self._serializar(usuario) for usuario in usuarios]
        return render(request, self.template_name, {
            "linhas": linhas,
            "usuarios_dados": linhas,
            "funcoes": FUNCOES,
            "busca": busca,
            "total_ativos": sum(1 for linha in linhas if linha["ativo"]),
        })

    @staticmethod
    def _serializar(usuario):
        grupos = nomes_das_funcoes(usuario)
        return {
            "id": usuario.pk,
            "username": usuario.username,
            "first_name": usuario.first_name,
            "last_name": usuario.last_name,
            "nome": usuario.get_full_name() or usuario.username,
            "email": usuario.email or "",
            "ativo": usuario.is_active,
            "superusuario": usuario.is_superuser,
            "funcoes": [
                funcao.codigo for funcao in FUNCOES
                if funcao.grupo in grupos
            ],
            "funcoes_titulos": [
                funcao.titulo for funcao in FUNCOES
                if funcao.grupo in grupos
            ],
        }

    def acao_save(self, request):
        bruto_id = (request.POST.get("id") or "").strip()
        usuario = (
            get_object_or_404(User, pk=int(bruto_id))
            if bruto_id.isdigit() else None
        )
        if usuario and usuario.is_superuser:
            raise ErroDeFormulario(
                "A conta superadministradora é protegida. Altere apenas os "
                "dados da própria conta na tela Minha conta."
            )

        username = texto(
            request, "username", obrigatorio=True,
            rotulo="o usuário", limite=150,
        )
        email = texto(request, "email", limite=254).lower()
        senha = request.POST.get("password") or ""
        codigos = request.POST.getlist("funcoes")

        if not codigos:
            raise ErroDeFormulario(
                "Escolha ao menos uma função. É ela que define o que a pessoa pode ver."
            )
        if email:
            try:
                validate_email(email)
            except ValidationError as exc:
                raise ErroDeFormulario("Informe um e-mail válido.") from exc

        repetido = User.objects.filter(username__iexact=username)
        email_repetido = User.objects.none()
        if email:
            email_repetido = User.objects.filter(email__iexact=email)
        if usuario:
            repetido = repetido.exclude(pk=usuario.pk)
            email_repetido = email_repetido.exclude(pk=usuario.pk)
        if repetido.exists():
            raise ErroDeFormulario("Esse nome de usuário já está em uso.")
        if email_repetido.exists():
            raise ErroDeFormulario("Esse e-mail já está em uso.")
        if usuario is None and len(senha) < 8:
            raise ErroDeFormulario("A senha inicial precisa ter pelo menos 8 caracteres.")
        if senha and len(senha) < 8:
            raise ErroDeFormulario("A nova senha precisa ter pelo menos 8 caracteres.")

        usuario = usuario or User()
        usuario.username = username
        usuario.first_name = texto(request, "first_name", limite=150)
        usuario.last_name = texto(request, "last_name", limite=150)
        usuario.email = email
        usuario.is_active = request.POST.get("is_active") == "on"
        if senha:
            usuario.set_password(senha)
        usuario.save()
        escolhidas = atribuir_funcoes(usuario, codigos)

        return self.sucesso(
            request,
            f"Acesso de {usuario.get_full_name() or usuario.username} salvo.",
            usuario=self._serializar(usuario),
            funcoes=[funcao.titulo for funcao in escolhidas],
        )

    def acao_alternar(self, request):
        usuario = get_object_or_404(User, pk=request.POST.get("id"))
        if usuario.is_superuser or usuario == request.user:
            raise ErroDeFormulario("Essa conta é protegida e não pode ser desativada aqui.")
        usuario.is_active = not usuario.is_active
        usuario.save(update_fields=["is_active"])
        return self.sucesso(
            request,
            f"{usuario.get_full_name() or usuario.username} "
            f"{'reativado' if usuario.is_active else 'desativado'}.",
        )
