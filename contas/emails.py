"""O e-mail de uma conta: normalizar, conferir se está livre e trocar.

O INCIDENTE. Uma conta de cliente apareceu com o mesmo e-mail de uma conta
da equipe comercial. Cada caminho que grava e-mail decidia sozinho se o
endereço estava livre, e cada um decidia de um jeito:

  * o cadastro do Google/Apple do allauth procura a conta pelo e-mail com
    igualdade EXATA no `User.email` (`filter_users_by_email`): uma conta da
    equipe gravada com maiúsculas ("Vendas@...", como o /system/ e o
    createsuperuser guardam) não era achada, e a conta nova nascia;
  * a tela "Meus e-mails" do allauth (/accounts/email/) acrescentava como
    endereço extra um e-mail que já era de OUTRA conta -- com a proteção
    contra enumeração ligada (o padrão), ela não recusa, só manda a
    confirmação;
  * o painel de equipe e a API conferiam só o `User.email`, sem os
    endereços extras do allauth;
  * ninguém conferia variantes Unicode: "ｖｅｎｄａｓ@..." (letras de largura
    total), um espaço invisível no meio do domínio ou o ponto final do
    domínio ("...com.br.") chegam à MESMA caixa de correio e passavam como
    endereços diferentes -- inclusive pelos gatilhos do banco, que comparam
    só `lower(trim(email))`.

A REGRA, AGORA EM UM LUGAR SÓ:

  1. `normalizar_email`: NFKC, sem espaço nem caractere invisível, em
     minúsculas, sem o ponto final do domínio. É o que se grava e o que se
     compara.
  2. Um endereço pertence a UMA conta, seja como e-mail principal
     (`User.email`), seja como endereço do allauth (`EmailAddress`).
  3. Os endereços da própria empresa (os do settings e os domínios
     lazersport) só entram em conta criada pela equipe -- ninguém se
     cadastra pelo site como "contato@lazersport...".

Quem garante: as telas chamam `validar_email_de_conta` (a mensagem certa
para a pessoa); `guarda.py` recusa no `pre_save` o que escapar (script,
admin, código futuro); o banco tem o índice único em `lower(email)` (a
migração contas/0003), contra duas gravações ao mesmo tempo.

O cadastro COMERCIAL de cliente (sistema_interno.Cliente) continua sendo
outra gaveta: o mesmo endereço pode estar numa conta e num cliente (é a
mesma pessoa nos dois papéis, ver `core/identidade_email.py`), e nenhum
caminho do sistema junta os dois pelo e-mail.
"""

from __future__ import annotations

import unicodedata
from email.utils import parseaddr

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction


MENSAGEM_EM_USO = (
    "Este e-mail já está em outra conta. Entre com ela ou use "
    "“Esqueci minha senha”."
)
MENSAGEM_RESERVADO = (
    "Este endereço é da própria Lazer & Sport e não pode ser usado numa "
    "conta de cliente. Use o seu e-mail pessoal."
)
MENSAGEM_INVALIDO = "Informe um e-mail válido."

#: Os domínios da casa. Endereço nestes domínios só em conta criada pela
#: equipe (painel ou /system/). Sobrescreva com CONTAS_DOMINIOS_RESERVADOS.
DOMINIOS_DA_EMPRESA = ("lazersport.com.br", "lazersport.com")


class EmailIndisponivel(ValidationError):
    """O endereço não pode ir para esta conta (inválido, em uso ou reservado).

    É um `ValidationError` do Django: formulário e serializer do DRF o
    mostram no campo sem conversão. `code` diz o motivo: "invalido",
    "em_uso" ou "reservado".
    """


class EmailEmUso(IntegrityError):
    """A guarda recusou gravar o e-mail de outra conta (ver guarda.py).

    É um IntegrityError de propósito: quem já trata a recusa do banco
    (RespostaJSONMixin, o middleware que traduz "ls_email_duplicado")
    trata esta também, com a mesma mensagem.
    """

    def __init__(self, email=""):
        super().__init__(
            "ls_email_duplicado_usuario: este e-mail já está em outra conta de acesso."
        )
        self.email = email


# ----------------------------------------------------------------------
# 1. Normalizar
# ----------------------------------------------------------------------
_CATEGORIAS_INVISIVEIS = {"Cf", "Cc", "Zs", "Zl", "Zp"}


def normalizar_email(valor) -> str:
    """O endereço como se grava e se compara: "" quando não há nada.

    NFKC junta as variantes de largura total e as ligaduras ("ｖｅｎｄａｓ" ->
    "vendas"); caractere de formatação (o espaço de largura zero, U+200B) e
    espaço somem -- o IDNA do domínio também os descarta, então são o mesmo
    destino; minúsculas; e o ponto final do domínio ("...com.br.") sai.
    """
    texto = unicodedata.normalize("NFKC", str(valor or ""))
    texto = "".join(
        c for c in texto
        if not c.isspace() and unicodedata.category(c) not in _CATEGORIAS_INVISIVEIS
    )
    texto = unicodedata.normalize("NFKC", texto.lower())
    if "@" in texto:
        local, _, dominio = texto.rpartition("@")
        texto = f"{local}@{dominio.rstrip('.')}"
    return texto


def dominio_de(email) -> str:
    email = normalizar_email(email)
    return email.rpartition("@")[2] if "@" in email else ""


# ----------------------------------------------------------------------
# 2. De quem é este endereço
# ----------------------------------------------------------------------
def contas_com_email(email, *, exceto=None) -> set[int]:
    """Os ids das contas que usam o endereço -- principal ou do allauth.

    Depois da migração contas/0002 todo e-mail gravado está normalizado (e
    a guarda mantém assim), então `iexact` com a forma normalizada acha
    qualquer variante que tenha sido gravada.
    """
    from allauth.account.models import EmailAddress

    chave = normalizar_email(email)
    if not chave:
        return set()
    User = get_user_model()
    ids = set(User.objects.filter(email__iexact=chave).values_list("pk", flat=True))
    ids |= set(EmailAddress.objects.filter(email__iexact=chave).values_list("user_id", flat=True))
    if exceto is not None:
        ids.discard(exceto)
    return ids


def conta_do_email(email):
    """A conta dona do endereço, ou None. Com mais de uma (dado antigo), None."""
    ids = contas_com_email(email)
    if len(ids) != 1:
        return None
    return get_user_model().objects.filter(pk=next(iter(ids))).first()


# ----------------------------------------------------------------------
# 3. Os endereços da empresa
# ----------------------------------------------------------------------
def emails_reservados() -> set[str]:
    """Os endereços da própria empresa, lidos do settings.

    CONTAS_EMAILS_RESERVADOS, quando existe, substitui a lista; sem ele,
    vale o contato da empresa, o da proposta, o de resposta, a conta do
    SMTP e o remetente.
    """
    lista = getattr(settings, "CONTAS_EMAILS_RESERVADOS", None)
    if lista is None:
        lista = [
            getattr(settings, nome, "")
            for nome in (
                "EMPRESA_EMAIL", "ORCAMENTO_EMAIL", "EMAIL_RESPOSTA",
                "EMAIL_HOST_USER", "DEFAULT_FROM_EMAIL", "PUSH_CONTATO",
            )
        ]
    reservados = set()
    for item in lista:
        item = str(item or "").strip()
        if item.lower().startswith("mailto:"):
            item = item[7:]
        endereco = normalizar_email(parseaddr(item)[1] or item)
        if "@" in endereco:
            reservados.add(endereco)
    return reservados


def dominios_reservados() -> tuple[str, ...]:
    dominios = getattr(settings, "CONTAS_DOMINIOS_RESERVADOS", DOMINIOS_DA_EMPRESA)
    return tuple(normalizar_email(d).lstrip("@") for d in dominios if d)


def e_reservado(email) -> bool:
    """O endereço é da empresa (da lista ou de um domínio da casa)?"""
    chave = normalizar_email(email)
    if not chave or "@" not in chave:
        return False
    if chave in emails_reservados():
        return True
    dominio = dominio_de(chave)
    return any(dominio == d or dominio.endswith("." + d) for d in dominios_reservados())


def _e_da_equipe(usuario) -> bool:
    if usuario is None or not getattr(usuario, "pk", None):
        return False
    if getattr(usuario, "is_staff", False) or getattr(usuario, "is_superuser", False):
        return True
    from sistema_interno.permissoes import NOMES_DOS_GRUPOS

    return usuario.groups.filter(name__in=NOMES_DOS_GRUPOS).exists()


# ----------------------------------------------------------------------
# 4. A conferência que toda tela usa
# ----------------------------------------------------------------------
def validar_email_de_conta(email, *, usuario=None, pela_equipe=False, obrigatorio=False) -> str:
    """O endereço normalizado, se ele pode ir para `usuario` -- senão EmailIndisponivel.

    `usuario`: a conta que vai receber o endereço (None numa conta nova).
    `pela_equipe`: quem grava é a equipe (painel, /system/) -- aí os
    endereços da empresa são aceitos. Pelo site, aplicativo e Google/Apple,
    não: a não ser que a conta já seja da equipe ou já tenha esse endereço.
    Vazio volta "" (quando `obrigatorio`, é recusado).
    """
    chave = normalizar_email(email)
    if not chave:
        if obrigatorio:
            raise EmailIndisponivel(MENSAGEM_INVALIDO, code="invalido")
        return ""
    try:
        validate_email(chave)
    except ValidationError as erro:
        raise EmailIndisponivel(MENSAGEM_INVALIDO, code="invalido") from erro

    usuario_id = getattr(usuario, "pk", None)
    if contas_com_email(chave, exceto=usuario_id):
        raise EmailIndisponivel(MENSAGEM_EM_USO, code="em_uso")

    if not pela_equipe and e_reservado(chave):
        ja_e_dela = usuario_id and normalizar_email(getattr(usuario, "email", "")) == chave
        if not ja_e_dela and not _e_da_equipe(usuario):
            raise EmailIndisponivel(MENSAGEM_RESERVADO, code="reservado")
    return chave


def mensagem_de(erro: ValidationError) -> str:
    return " ".join(getattr(erro, "messages", None) or [str(erro)])


# ----------------------------------------------------------------------
# 5. Trocar o e-mail, com os endereços do allauth acompanhando
# ----------------------------------------------------------------------
@transaction.atomic
def sincronizar_enderecos(usuario, *, verificado=False):
    """Deixa os endereços do allauth de acordo com o `User.email`.

    O e-mail principal vira o endereço principal (criado se faltar). Os
    endereços NÃO confirmados que sobraram de um e-mail antigo saem: eles
    seguravam o endereço velho para esta conta (e serviam para entrar por
    ele) sem ninguém ter provado que eram dela. Os confirmados ficam, como
    secundários. `verificado` marca o principal como confirmado (o Google
    confirmou, por exemplo).
    """
    from allauth.account.models import EmailAddress

    if not getattr(usuario, "pk", None):
        return None
    atual = normalizar_email(usuario.email)
    enderecos = list(EmailAddress.objects.filter(user=usuario))
    principal = None
    for endereco in enderecos:
        mesmo = bool(atual) and normalizar_email(endereco.email) == atual
        if mesmo and principal is None:
            principal = endereco
        elif mesmo:
            # a mesma caixa gravada duas vezes (maiúsculas, dado antigo)
            principal.verified = principal.verified or endereco.verified
            endereco.delete()
        elif not endereco.verified:
            endereco.delete()
        elif endereco.primary:
            endereco.primary = False
            endereco.save(update_fields=["primary"])
    if not atual:
        return None
    if principal is None:
        principal = EmailAddress(user=usuario, email=atual)
    principal.email = atual
    principal.primary = True
    principal.verified = bool(principal.verified or verificado)
    principal.save()
    return principal


@transaction.atomic
def trocar_email(usuario, novo, *, pela_equipe=False, verificado=False) -> str:
    """Confere, grava o `User.email` e acerta os endereços do allauth.

    Levanta EmailIndisponivel antes de gravar qualquer coisa.
    """
    novo = validar_email_de_conta(novo, usuario=usuario, pela_equipe=pela_equipe)
    if normalizar_email(usuario.email) != novo or usuario.email != novo:
        usuario.email = novo
        usuario.save(update_fields=["email"])
    sincronizar_enderecos(usuario, verificado=verificado)
    return novo
