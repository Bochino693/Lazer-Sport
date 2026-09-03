import unicodedata

from django.urls import reverse
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import ClientePerfil


def _slug_username(base: str) -> str:
    base = (base or "").strip().lower()
    if "@" in base:
        base = base.split("@", 1)[0]
    base = unicodedata.normalize("NFKD", base)
    base = base.encode("ascii", "ignore").decode("ascii")
    base = "".join(c if c.isalnum() else "." for c in base).strip(".")
    while ".." in base:
        base = base.replace("..", ".")
    return base[:150] or "cliente"


def _nome_do_social(sociallogin, user):
    extra = getattr(sociallogin.account, "extra_data", {}) or {}
    primeiro = extra.get("given_name") or extra.get("first_name") or ""
    ultimo = extra.get("family_name") or extra.get("last_name") or ""
    nome_cru = extra.get("name")

    if isinstance(nome_cru, dict):
        primeiro = primeiro or nome_cru.get("firstName") or ""
        ultimo = ultimo or nome_cru.get("lastName") or ""
    elif isinstance(nome_cru, str) and nome_cru.strip() and not primeiro:
        partes = nome_cru.strip().split()
        primeiro = partes[0]
        ultimo = " ".join(partes[1:])

    primeiro = (primeiro or user.first_name or "").strip()
    ultimo = (ultimo or user.last_name or "").strip()
    return f"{primeiro} {ultimo}".strip(), primeiro, ultimo


def sincronizar_perfil(user, nome_completo: str = "") -> ClientePerfil:
    perfil, _ = ClientePerfil.objects.get_or_create(user=user)
    nome = (nome_completo or f"{user.first_name} {user.last_name}").strip()
    if nome and not (perfil.nome_completo or "").strip():
        perfil.nome_completo = nome[:150]
        perfil.save(update_fields=["nome_completo"])
    return perfil


class AccountAdapter(DefaultAccountAdapter):
    def validate_unique_email(self, email):
        from django.core.exceptions import ValidationError
        from .identidade_email import validar_email_de_usuario
        from sistema_interno.utils import ErroDeFormulario
        email = super().validate_unique_email(email)
        # Cadastro/alteração usa a mesma identidade dos clientes do painel.
        user = getattr(self.request, "user", None)
        try:
            return validar_email_de_usuario(email, usuario_id=user.pk if user and user.is_authenticated else None)
        except ErroDeFormulario as exc:
            raise ValidationError(str(exc)) from exc

    def generate_unique_username(self, txts, regex=None):
        from django.contrib.auth.models import User

        base = ""
        for txt in txts:
            if txt:
                base = _slug_username(txt)
                if base:
                    break

        base = base or "cliente"
        username = base
        contador = 1
        while User.objects.filter(username__iexact=username).exists():
            contador += 1
            username = f"{base}{contador}"[:150]
        return username

    def get_login_redirect_url(self, request):
        url_padrao = super().get_login_redirect_url(request)
        request.session.setdefault("conta_fluxo_tipo", "login")

        if url_padrao and url_padrao not in {
            reverse("completar_perfil"),
            reverse("conta_transicao"),
        }:
            request.session["conta_fluxo_destino"] = url_padrao

        perfil = sincronizar_perfil(request.user)
        if not (perfil.telefone or "").strip():
            return f"{reverse('completar_perfil')}#telefone-box"

        return reverse("conta_transicao")


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        _, primeiro, ultimo = _nome_do_social(sociallogin, user)

        if primeiro and not user.first_name:
            user.first_name = primeiro[:150]
        if ultimo and not user.last_name:
            user.last_name = ultimo[:150]

        email = (data.get("email") or user.email or "").strip()
        if email and not user.email:
            user.email = email
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        nome_completo, _, _ = _nome_do_social(sociallogin, user)
        sincronizar_perfil(user, nome_completo)
        request.session["conta_fluxo_tipo"] = "cadastro"
        return user

    def pre_social_login(self, request, sociallogin):
        request.session["conta_fluxo_tipo"] = "login"

        if sociallogin.is_existing or request.user.is_authenticated:
            return

        email = (sociallogin.user.email or "").strip().lower()
        if not email:
            return

        verificado = any(
            (endereco.email or "").strip().lower() == email and endereco.verified
            for endereco in sociallogin.email_addresses
        )
        if not verificado:
            return

        from django.contrib.auth.models import User
        from allauth.account.models import EmailAddress

        registro = EmailAddress.objects.filter(email__iexact=email).first()
        usuario = registro.user if registro else None
        if usuario is None:
            usuario = User.objects.filter(email__iexact=email).first()

        if usuario:
            sociallogin.connect(request, usuario)
