"""A última trava: nenhuma conta é gravada com o e-mail de outra.

As telas conferem antes (emails.validar_email_de_conta) e mostram a
mensagem certa. Esta guarda existe para o que não passa por tela nenhuma:
o /system/, um comando, um script no shell, o allauth gravando por conta
própria, o código que alguém escrever amanhã. Toda gravação de `User` e
de `EmailAddress` (o endereço do allauth) passa por aqui:

  * o e-mail é gravado NORMALIZADO (emails.normalizar_email) -- o que o
    índice único do banco (lower(email), migração contas/0003) e os
    gatilhos antigos comparam é a mesma coisa que a tela comparou;
  * se o endereço mudou e já é de outra conta, a gravação é recusada com
    `EmailEmUso` (um IntegrityError).

Custa uma consulta só quando o e-mail MUDA: o `last_login` de cada entrada,
o perfil salvo sem trocar o e-mail e as listas de contas não pagam nada.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_init, post_save, pre_save

from .emails import EmailEmUso, contas_com_email, normalizar_email

_AUSENTE = object()
_ATRIBUTO = "_contas_email_lido"


def _lembrar(sender, instance, **kwargs):
    # __dict__, e não instance.email: com .only()/.defer() o campo pode não
    # ter vindo, e ler o atributo faria uma consulta por objeto.
    setattr(instance, _ATRIBUTO, instance.__dict__.get("email", _AUSENTE))


def _mudou(instance, normalizado) -> bool:
    if instance._state.adding or instance.pk is None:
        return True
    lido = getattr(instance, _ATRIBUTO, _AUSENTE)
    if lido is _AUSENTE:
        return True
    return normalizar_email(lido) != normalizado


def _conferir(instance, *, dono_id, update_fields, raw):
    if raw:
        return
    if update_fields is not None and "email" not in update_fields:
        return
    if "email" not in instance.__dict__:
        return
    normalizado = normalizar_email(instance.email)
    if instance.email != normalizado:
        instance.email = normalizado
    if not normalizado or not _mudou(instance, normalizado):
        return
    if contas_com_email(normalizado, exceto=dono_id):
        raise EmailEmUso(normalizado)


def _guardar_usuario(sender, instance, update_fields=None, raw=False, **kwargs):
    _conferir(instance, dono_id=instance.pk, update_fields=update_fields, raw=raw)


def _guardar_endereco(sender, instance, update_fields=None, raw=False, **kwargs):
    _conferir(instance, dono_id=instance.user_id, update_fields=update_fields, raw=raw)


def ligar():
    from allauth.account.models import EmailAddress

    User = get_user_model()
    for modelo, guarda in ((User, _guardar_usuario), (EmailAddress, _guardar_endereco)):
        rotulo = modelo._meta.label_lower
        post_init.connect(_lembrar, sender=modelo, dispatch_uid=f"contas.lembrar.{rotulo}")
        post_save.connect(_lembrar, sender=modelo, dispatch_uid=f"contas.relembrar.{rotulo}")
        pre_save.connect(guarda, sender=modelo, dispatch_uid=f"contas.guarda.{rotulo}")
