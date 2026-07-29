# core/adapters.py
"""
Adaptadores do django-allauth (65.x) para o Lazer & Sport.

Objetivo: quando o cliente entra com Google ou Apple, o cadastro tem que
sair pronto sem ele digitar nada. O que o provedor devolve (nome,
sobrenome, e-mail) é gravado direto no User e espelhado no ClientePerfil.

O que nenhum provedor devolve é telefone -- esse é o único campo que
ainda precisa ser pedido, e isso acontece uma única vez na tela
/completar-perfil/ (ver core/views_conta.py).
"""

import unicodedata

from django.urls import reverse

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import ClientePerfil


# ============================================================
# HELPERS
# ============================================================

def _slug_username(base: str) -> str:
    """
    Gera um username limpo a partir do e-mail ou do nome.
    'João da Silva' -> 'joao.da.silva' | 'joao@gmail.com' -> 'joao'
    """
    base = (base or "").strip().lower()
    if "@" in base:
        base = base.split("@")[0]

    base = unicodedata.normalize("NFKD", base)
    base = base.encode("ascii", "ignore").decode("ascii")
    base = "".join(c if c.isalnum() else "." for c in base).strip(".")

    while ".." in base:
        base = base.replace("..", ".")

    return base[:150] or "cliente"


def _nome_do_social(sociallogin, user):
    """
    Devolve (nome_completo, primeiro_nome, sobrenome) a partir do que o
    provedor mandou.

    Google: extra_data traz 'given_name', 'family_name' e 'name' (string).
    Apple: manda o nome UMA ÚNICA VEZ, na primeira autorização, aninhado
    em {'name': {'firstName': ..., 'lastName': ...}}. Depois disso a
    Apple nunca mais reenvia -- por isso gravamos já no primeiro login e
    nunca sobrescrevemos com vazio.
    """
    extra = getattr(sociallogin.account, "extra_data", {}) or {}

    primeiro = extra.get("given_name") or extra.get("first_name") or ""
    ultimo = extra.get("family_name") or extra.get("last_name") or ""

    nome_cru = extra.get("name")

    # Formato Apple: dicionário aninhado
    if isinstance(nome_cru, dict):
        primeiro = primeiro or nome_cru.get("firstName") or ""
        ultimo = ultimo or nome_cru.get("lastName") or ""

    # Formato Google: string única ("João da Silva")
    elif isinstance(nome_cru, str) and nome_cru.strip() and not primeiro:
        partes = nome_cru.strip().split()
        primeiro = partes[0]
        ultimo = " ".join(partes[1:])

    primeiro = (primeiro or user.first_name or "").strip()
    ultimo = (ultimo or user.last_name or "").strip()

    return f"{primeiro} {ultimo}".strip(), primeiro, ultimo


def sincronizar_perfil(user, nome_completo: str = "") -> ClientePerfil:
    """
    Garante o ClientePerfil e preenche nome_completo sem nunca apagar
    um valor que o cliente já tenha editado à mão.
    """
    perfil, _ = ClientePerfil.objects.get_or_create(user=user)

    nome = (nome_completo or f"{user.first_name} {user.last_name}").strip()

    if nome and not (perfil.nome_completo or "").strip():
        perfil.nome_completo = nome[:150]
        perfil.save(update_fields=["nome_completo"])

    return perfil


# ============================================================
# ADAPTER DE CONTA (login normal + redirecionamentos)
# ============================================================

class AccountAdapter(DefaultAccountAdapter):

    def generate_unique_username(self, txts, regex=None):
        """
        Sem isso o allauth cria usernames feios tipo 'joao123abc'.
        Aqui o username sai de e-mail/nome e só ganha sufixo numérico
        se já existir alguém com o mesmo.
        """
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
        """
        Depois de logar: se ainda falta telefone (caso típico de quem
        entrou por Google/Apple), manda uma única vez pra tela de
        completar perfil. Se o cliente escolher "Agora não", a flag de
        sessão evita que ele seja empurrado de novo na mesma visita.
        """
        url_padrao = super().get_login_redirect_url(request)

        if request.session.get("pulou_completar_perfil"):
            return url_padrao

        perfil = getattr(request.user, "perfil", None)
        if perfil and not (perfil.telefone or "").strip():
            return reverse("completar_perfil")

        return url_padrao


# ============================================================
# ADAPTER SOCIAL (Google / Apple)
# ============================================================

class SocialAccountAdapter(DefaultSocialAccountAdapter):

    def populate_user(self, request, sociallogin, data):
        """
        Roda ANTES de salvar o usuário novo. É aqui que o cadastro
        deixa de precisar de digitação: nome, sobrenome e e-mail vêm
        prontos do provedor.
        """
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
        """
        Depois que o User existe, espelha o nome no ClientePerfil.
        O signal post_save já criou o perfil; aqui só completamos.
        """
        user = super().save_user(request, sociallogin, form)

        nome_completo, _, _ = _nome_do_social(sociallogin, user)
        sincronizar_perfil(user, nome_completo)

        return user

    def pre_social_login(self, request, sociallogin):
        """
        Cliente que já tem conta por e-mail/senha e depois clica em
        "Entrar com Google": o e-mail do Google é verificado, então
        conectamos ao usuário existente em vez de mostrar erro de
        e-mail duplicado.

        Isso só é seguro porque Google e Apple entregam e-mail
        verificado. Nunca habilite o mesmo comportamento para provedor
        que não verifica e-mail.
        """
        if sociallogin.is_existing:
            return

        # Perfil de quem já estava logado e está apenas conectando
        if request.user.is_authenticated:
            return

        email = (sociallogin.user.email or "").strip().lower()
        if not email:
            return

        # Só conecta se o PROVEDOR garantir que o e-mail é verificado.
        # Sem essa checagem, um provedor que aceitasse e-mail arbitrário
        # permitiria sequestrar a conta de qualquer cliente.
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

        # Contas criadas pelo cadastro manual do site podem não ter
        # registro em EmailAddress -- por isso o fallback pelo User.
        if usuario is None:
            usuario = User.objects.filter(email__iexact=email).first()

        if usuario:
            sociallogin.connect(request, usuario)