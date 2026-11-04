"""
Fluxo público de conta da Lazer & Sport.

Este arquivo concentra somente:
- login manual;
- cadastro manual;
- conclusão obrigatória do telefone após Google/Apple;
- tela única de confirmação;
- logout.

As demais telas permanecem em core/views.py.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from .forms import CadastroForm, CompletarPerfilForm
from .models import ClientePerfil


TIPOS_FLUXO = {"cadastro", "login"}


def _nome_exibicao(user: User) -> str:
    """Nome amigável, sem expor um username técnico como gerente123."""
    nome = (user.get_full_name() or "").strip()
    if nome:
        return nome

    email = (user.email or "").strip()
    if email:
        return email.split("@", 1)[0]

    return "Cliente"


def _perfil_do_usuario(user: User) -> ClientePerfil:
    perfil, _ = ClientePerfil.objects.get_or_create(user=user)
    return perfil


def _telefone_preenchido(user: User) -> bool:
    perfil = _perfil_do_usuario(user)
    return bool((perfil.telefone or "").strip())


def _limpar_mensagens_automaticas(request) -> None:
    """
    Consome mensagens deixadas pelo allauth, como "Registrado com ...".

    Os erros dos formulários continuam aparecendo porque são renderizados
    diretamente por CadastroForm/CompletarPerfilForm. Erros do login manual
    são criados somente quando a própria tela de login é renderizada.
    """
    for _ in get_messages(request):
        pass


def _destino_seguro(request, destino: str | None, padrao: str = "home") -> str:
    destino = (destino or "").strip()

    if destino and url_has_allowed_host_and_scheme(
        url=destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return destino

    return reverse(padrao)


def _guardar_fluxo(
    request,
    *,
    tipo: str,
    destino: str | None = None,
) -> None:
    request.session["conta_fluxo_tipo"] = (
        tipo if tipo in TIPOS_FLUXO else "login"
    )

    if destino:
        request.session["conta_fluxo_destino"] = _destino_seguro(
            request,
            destino,
        )


def enviar_confirmacao_de_email(request, usuario) -> bool:
    """Manda o e-mail de confirmação do endereço (allauth), sem travar o cadastro.

    A conta entra e compra sem confirmar (ACCOUNT_EMAIL_VERIFICATION =
    "optional"); confirmar só diz que o e-mail é da pessoa. Falha de SMTP
    não pode derrubar o cadastro: vira log e a pessoa pede de novo depois.
    """
    if not (usuario.email or "").strip():
        return False
    # Na API o visitante chega com request.user = None (UNAUTHENTICATED_USER
    # = None): os context processors do e-mail esperam um usuário.
    if getattr(request, "user", None) is None:
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
    try:
        from allauth.account.models import EmailAddress

        endereco, _ = EmailAddress.objects.get_or_create(
            user=usuario,
            email__iexact=usuario.email,
            defaults={"email": usuario.email, "primary": True, "verified": False},
        )
        if endereco.verified:
            return False
        endereco.send_confirmation(request, signup=True)
        return True
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("E-mail de confirmação não enviado para %s", usuario.email)
        return False


def _redirecionar_para_telefone():
    """O fragmento faz o navegador chegar e rolar até o campo."""
    return redirect(f"{reverse('completar_perfil')}#telefone-box")


class ContaTransicaoView(LoginRequiredMixin, View):
    """Aviso moderno compartilhado por cadastro manual e qualquer login."""

    template_name = "conta_transicao.html"
    login_url = "login"

    def get(self, request):
        # Nem a tela de sucesso pode ser acessada sem telefone.
        if not _telefone_preenchido(request.user):
            return _redirecionar_para_telefone()

        _limpar_mensagens_automaticas(request)

        modo = request.session.pop("conta_fluxo_tipo", "login")
        if modo not in TIPOS_FLUXO:
            modo = "login"

        destino = _destino_seguro(
            request,
            request.session.pop("conta_fluxo_destino", None),
        )

        return render(
            request,
            self.template_name,
            {
                "modo": modo,
                "nome_exibicao": _nome_exibicao(request.user),
                "destino_url": destino,
                "tempo_redirecionamento": 3200,
            },
        )


class LoginUsuarioView(View):
    template_name = "login.html"

    def get(self, request):
        if request.user.is_authenticated:
            if not _telefone_preenchido(request.user):
                _guardar_fluxo(request, tipo="login")
                return _redirecionar_para_telefone()
            return redirect("home")

        return render(
            request,
            self.template_name,
            {
                "next": _destino_seguro(
                    request,
                    request.GET.get("next"),
                ),
            },
        )

    def post(self, request):
        login_digitado = (request.POST.get("username") or "").strip()
        senha = request.POST.get("password") or ""

        username = login_digitado

        if "@" in login_digitado:
            usuario_email = (
                User.objects
                .filter(email__iexact=login_digitado)
                .order_by("id")
                .first()
            )
            username = usuario_email.username if usuario_email else ""

        usuario = authenticate(
            request,
            username=username,
            password=senha,
        )

        if usuario is None:
            messages.error(
                request,
                "Usuário, e-mail ou senha incorretos.",
            )
            return render(
                request,
                self.template_name,
                {
                    "login_digitado": login_digitado,
                    "next": _destino_seguro(
                        request,
                        request.POST.get("next"),
                    ),
                },
            )

        login(
            request,
            usuario,
            backend="django.contrib.auth.backends.ModelBackend",
        )

        _guardar_fluxo(
            request,
            tipo="login",
            destino=request.POST.get("next"),
        )

        if not _telefone_preenchido(usuario):
            return _redirecionar_para_telefone()

        # Com a âncora: a tela de transição é longa e sem ela o cliente caía
        # no topo, sem ver o card de boas-vindas que é o ponto da página.
        return redirect(f"{reverse('conta_transicao')}#conta-criada")


class RegistrarView(View):
    template_name = "register.html"

    def get(self, request):
        if request.user.is_authenticated:
            if not _telefone_preenchido(request.user):
                _guardar_fluxo(request, tipo="cadastro")
                return _redirecionar_para_telefone()
            return redirect("home")

        # Quem chega de um jogo (a partida grátis acabou) volta para ele
        # depois do cadastro: a tela de transição usa este destino.
        destino = request.GET.get("next")
        if destino:
            request.session["conta_fluxo_destino"] = _destino_seguro(request, destino)

        return render(
            request,
            self.template_name,
            self._contexto(CadastroForm()),
        )

    @staticmethod
    def _contexto(form):
        """O formulário mais o desafio de robô (selo e pergunta): ver core/captcha.py."""
        from django.conf import settings

        from . import captcha

        desafio = captcha.novo_desafio()
        return {
            "form": form,
            "selo_cadastro": desafio["selo"],
            "imagem_humana": desafio["imagem"],
            "turnstile_site_key": settings.TURNSTILE_SITE_KEY if captcha.turnstile_ativo() else "",
        }

    @transaction.atomic
    def post(self, request):
        form = CadastroForm(request.POST, request=request)

        if not form.is_valid():
            # o erro do freio (robô, limite por IP) é de formulário inteiro:
            # a mensagem vai no topo, não em "confira os campos"
            if not form.non_field_errors():
                messages.error(
                    request,
                    "Confira os campos destacados e tente novamente.",
                )
            return render(
                request,
                self.template_name,
                self._contexto(form),
            )

        usuario = form.salvar()

        # Cadastro manual somente termina se o telefone foi realmente salvo.
        if not _telefone_preenchido(usuario):
            raise RuntimeError(
                "Cadastro manual interrompido: telefone não foi salvo."
            )

        login(
            request,
            usuario,
            backend="django.contrib.auth.backends.ModelBackend",
        )

        _guardar_fluxo(request, tipo="cadastro")
        enviar_confirmacao_de_email(request, usuario)

        return redirect(
            f"{reverse('conta_transicao')}#conta-criada"
        )


class DesafioHumanoView(View):
    """Uma imagem nova para o cadastro (o botão "Outra imagem"), em JSON: {"selo", "imagem"}."""

    def get(self, request):
        from django.http import JsonResponse

        from . import captcha

        desafio = captcha.novo_desafio()
        resposta = JsonResponse({"selo": desafio["selo"], "imagem": desafio["imagem"]})
        resposta["Cache-Control"] = "no-store"
        return resposta


class CompletarPerfilView(LoginRequiredMixin, View):
    """
    Etapa obrigatória para contas Google/Apple e contas antigas sem telefone.

    Não existe opção de pular. Enquanto o número não for válido, o cliente
    permanece nesta tela e o middleware bloqueia o restante do site.
    """

    template_name = "completar_perfil.html"
    login_url = "login"

    def get(self, request):
        _limpar_mensagens_automaticas(request)
        perfil = _perfil_do_usuario(request.user)

        if (perfil.telefone or "").strip():
            return redirect(
                f"{reverse('conta_transicao')}#conta-criada"
            )

        request.session.setdefault("conta_fluxo_tipo", "cadastro")

        return render(
            request,
            self.template_name,
            {
                "form": CompletarPerfilForm(instance=perfil),
                "perfil": perfil,
                "forcar_foco_telefone": True,
            },
        )

    @transaction.atomic
    def post(self, request):
        perfil = _perfil_do_usuario(request.user)
        form = CompletarPerfilForm(request.POST, instance=perfil)

        if form.is_valid():
            perfil = form.save()
            perfil.refresh_from_db(fields=["telefone"])

            if not (perfil.telefone or "").strip():
                form.add_error(
                    "telefone",
                    "O telefone é obrigatório para concluir seu cadastro.",
                )
            else:
                return redirect(
                    f"{reverse('conta_transicao')}#conta-criada"
                )

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "perfil": perfil,
                "forcar_foco_telefone": True,
            },
            status=400,
        )


class LogoutUsuarioView(View):
    """Usa a mesma tela moderna da entrada, mas em modo de saída."""

    template_name = "conta_transicao.html"

    def get(self, request):
        nome = (
            _nome_exibicao(request.user)
            if request.user.is_authenticated
            else ""
        )

        logout(request)
        _limpar_mensagens_automaticas(request)

        return render(
            request,
            self.template_name,
            {
                "modo": "logout",
                "nome_exibicao": nome,
                "destino_url": reverse("login"),
                "tempo_redirecionamento": 2600,
            },
        )