"""O allauth (cadastro pelo /accounts/, Google e Apple) pelas regras da casa.

Moravam em core/adapters.py, que continua existindo só para quem importa
de lá. O que é novo aqui é o e-mail:

  * `clean_email` NORMALIZA (emails.normalizar_email) tudo o que o allauth
    lê: cadastro, "Meus e-mails" e a recuperação de senha;
  * `validate_unique_email` confere pela mesma regra das outras telas -- o
    `User.email` e os endereços do allauth, sem diferença de maiúsculas
    nem de variante Unicode, e os endereços da empresa;
  * no login social (`pre_social_login`), o e-mail que o Google/Apple traz
    só liga a pessoa a uma conta que já existe quando o PROVEDOR GARANTE
    que o endereço é dela (`email_verified`) -- senão qualquer um criaria
    uma conta no Google com o e-mail de outra pessoa e entraria na conta
    dela. Sem a garantia, a entrada é recusada com explicação, e uma
    segunda conta com o mesmo e-mail NUNCA é criada;
  * com a garantia, liga só à conta daquele e-mail (havendo uma só) e
    marca o endereço como confirmado. Numa conta de cliente cujo e-mail
    nunca foi confirmado, a senha local é desativada -- quem cadastrou o
    e-mail de outra pessoa com uma senha não continua entrando (é o que o
    próprio allauth faz quando acha a conta pelo e-mail). Conta da equipe
    (criada pela empresa) mantém a senha: o painel entra com ela.
"""

from __future__ import annotations

import logging
import unicodedata

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from . import emails as regras

log = logging.getLogger(__name__)

#: Provedores em que o `email_verified` vale como prova de dono do endereço.
PROVEDORES_CONFIAVEIS = ("google", "apple")


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


def username_livre(*sugestoes) -> str:
    """Um nome de usuário que ninguém usa, a partir da primeira sugestão boa."""
    from django.contrib.auth.models import User

    base = ""
    for sugestao in sugestoes:
        if sugestao:
            base = _slug_username(sugestao)
            if base:
                break
    base = base or "cliente"
    username = base
    contador = 1
    while User.objects.filter(username__iexact=username).exists():
        contador += 1
        username = f"{base}{contador}"[:150]
    return username


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


def sincronizar_perfil(user, nome_completo: str = ""):
    from core.models import ClientePerfil

    perfil, _ = ClientePerfil.objects.get_or_create(user=user)
    nome = (nome_completo or f"{user.first_name} {user.last_name}").strip()
    if nome and not (perfil.nome_completo or "").strip():
        perfil.nome_completo = nome[:150]
        perfil.save(update_fields=["nome_completo"])
    return perfil


def _cadastro_aberto(request) -> bool:
    """O freio de contas falsas: contas demais do mesmo IP fecham o cadastro por um tempo."""
    from core.registro_cadastro import limite_de_cadastros_estourado

    return not limite_de_cadastros_estourado(request)


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return super().is_open_for_signup(request) and _cadastro_aberto(request)

    def clean_email(self, email):
        return regras.normalizar_email(super().clean_email(email))

    def validate_unique_email(self, email):
        email = super().validate_unique_email(email)
        user = getattr(self.request, "user", None)
        usuario = user if user is not None and user.is_authenticated else None
        # EmailIndisponivel já é um ValidationError: o formulário o mostra no campo.
        return regras.validar_email_de_conta(email, usuario=usuario)

    def generate_unique_username(self, txts, regex=None):
        return username_livre(*txts)

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


# ----------------------------------------------------------------------
# Login social
# ----------------------------------------------------------------------
def emails_do_login(sociallogin) -> list[str]:
    """Todos os endereços que o provedor mandou, normalizados, sem repetir."""
    vistos = []
    for endereco in list(sociallogin.email_addresses or []) + [sociallogin.user]:
        email = regras.normalizar_email(getattr(endereco, "email", ""))
        if email and email not in vistos:
            vistos.append(email)
    return vistos


def emails_garantidos(sociallogin) -> set[str]:
    """Os endereços que o provedor GARANTE que são da pessoa."""
    if sociallogin.account.provider not in PROVEDORES_CONFIAVEIS:
        return set()
    return {
        regras.normalizar_email(endereco.email)
        for endereco in (sociallogin.email_addresses or [])
        if endereco.verified and endereco.email
    }


def _registrar_recusa(request, sociallogin, *, conta=None, email="", motivo=""):
    from core.registro_cadastro import ip_da_requisicao

    from .models import OcorrenciaSeguranca

    try:
        ip, _ = ip_da_requisicao(request)
        OcorrenciaSeguranca.objects.create(
            tipo=OcorrenciaSeguranca.Tipo.SOCIAL_RECUSADO,
            usuario=conta,
            username=(getattr(conta, "username", "") or "")[:150],
            login_tentado=email[:254],
            ip=ip,
            origem=(sociallogin.account.provider or "social")[:20],
            motivo=motivo,
        )
    except Exception:  # noqa: BLE001 -- a recusa vale mesmo sem o registro
        log.exception("A recusa do login social não foi registrada.")


def _recusar(request, mensagem):
    messages.error(request, mensagem, extra_tags="titulo:Não foi possível entrar")
    raise ImmediateHttpResponse(redirect("login"))


def _e_da_equipe(usuario) -> bool:
    return regras._e_da_equipe(usuario)


def _confirmar_endereco(conta, email):
    """O provedor garantiu que `email` é de `conta`: o endereço fica confirmado."""
    from allauth.account.models import EmailAddress

    atualizados = EmailAddress.objects.filter(user=conta, email__iexact=email).update(verified=True)
    if not atualizados and regras.normalizar_email(conta.email) == email:
        regras.sincronizar_enderecos(conta, verificado=True)


def ligar_a_conta(request, sociallogin, conta, email):
    """Liga o login social à conta do e-mail que o provedor garantiu."""
    from allauth.account.models import EmailAddress

    endereco = EmailAddress.objects.filter(user=conta, email__iexact=email).first()
    confirmado = bool(endereco and endereco.verified)
    if not confirmado and not _e_da_equipe(conta) and conta.has_usable_password():
        # Alguém pode ter cadastrado o e-mail desta pessoa com uma senha
        # que ela não conhece: daqui em diante, só entra quem tem o e-mail.
        conta.set_unusable_password()
        conta.save(update_fields=["password"])
    _confirmar_endereco(conta, email)
    sociallogin.connect(request, conta)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        # Google/Apple criam conta sem formulário: o limite por IP é o único freio
        return super().is_open_for_signup(request, sociallogin) and _cadastro_aberto(request)

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        _, primeiro, ultimo = _nome_do_social(sociallogin, user)

        if primeiro and not user.first_name:
            user.first_name = primeiro[:150]
        if ultimo and not user.last_name:
            user.last_name = ultimo[:150]

        email = regras.normalizar_email(data.get("email") or user.email or "")
        user.email = email
        for endereco in sociallogin.email_addresses or []:
            endereco.email = regras.normalizar_email(endereco.email)
        return user

    def save_user(self, request, sociallogin, form=None):
        # Última conferência antes de a conta nascer (a guarda do pre_save
        # também recusaria, mas sem explicar nada à pessoa).
        for email in emails_do_login(sociallogin):
            if regras.contas_com_email(email):
                _recusar(request, regras.MENSAGEM_EM_USO)
        user = super().save_user(request, sociallogin, form)
        nome_completo, _, _ = _nome_do_social(sociallogin, user)
        sincronizar_perfil(user, nome_completo)
        request.session["conta_fluxo_tipo"] = "cadastro"
        return user

    def pre_social_login(self, request, sociallogin):
        request.session["conta_fluxo_tipo"] = "login"

        garantidos = emails_garantidos(sociallogin)

        if sociallogin.is_existing:
            # Achado pela conta social já ligada ou pelo allauth, pelo e-mail
            # garantido. Conta da equipe: o endereço passa a confirmado ANTES
            # de o allauth decidir apagar a senha (o painel entra com ela).
            email = regras.normalizar_email(getattr(sociallogin, "_did_authenticate_by_email", "") or "")
            if email and email in garantidos and _e_da_equipe(sociallogin.user):
                _confirmar_endereco(sociallogin.user, email)
            return

        if request.user.is_authenticated:
            # "Conectar" o Google a quem já está logado: é a própria pessoa
            # escolhendo, e o e-mail do provedor não vira endereço da conta.
            return

        emails = emails_do_login(sociallogin)
        donos = {}
        for email in emails:
            for conta_id in regras.contas_com_email(email):
                donos.setdefault(conta_id, email)

        if not donos:
            reservado = next((e for e in emails if regras.e_reservado(e)), "")
            if reservado:
                _registrar_recusa(
                    request, sociallogin, email=reservado,
                    motivo="Conta nova pelo login social com um endereço da própria empresa.",
                )
                _recusar(request, regras.MENSAGEM_RESERVADO)
            return  # e-mail livre: o cadastro automático segue

        from django.contrib.auth.models import User

        if len(donos) > 1:
            _registrar_recusa(
                request, sociallogin, email=next(iter(donos.values())),
                motivo="O e-mail do login social aparece em mais de uma conta.",
            )
            _recusar(request, "Este e-mail aparece em mais de uma conta. Fale com a gente pelo WhatsApp.")

        conta_id, email = next(iter(donos.items()))
        conta = User.objects.get(pk=conta_id)
        if email not in garantidos:
            _registrar_recusa(
                request, sociallogin, conta=conta, email=email,
                motivo=(
                    f"O {sociallogin.account.provider.title()} trouxe o e-mail de uma conta que já "
                    "existe sem garantir que o endereço é da pessoa: não foi ligado nem criada outra conta."
                ),
            )
            _recusar(
                request,
                "Já existe uma conta com este e-mail. Entre com o seu usuário e senha "
                "(ou use “Esqueci minha senha”): o provedor não confirmou que o e-mail é seu.",
            )

        ligar_a_conta(request, sociallogin, conta, email)

