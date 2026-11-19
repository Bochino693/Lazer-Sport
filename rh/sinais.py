"""Apagar o documento no banco apaga o arquivo -- depois do commit.

Se a transação desfizer a exclusão, o arquivo continua lá: apagar antes do
commit deixaria uma linha apontando para um arquivo que não existe.
"""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Colaborador, DocumentoColaborador, TermoExclusividade


@receiver(post_delete, sender=DocumentoColaborador)
def apagar_arquivo(sender, instance, **kwargs):
    nome = instance.arquivo.name if instance.arquivo else ""
    if not nome:
        return
    armazenamento = instance.arquivo.storage
    transaction.on_commit(lambda: armazenamento.delete(nome))


# A faixa do termo, guardada por pessoa (rh/templatetags/rh_extras.py): uma
# ficha ou um termo salvo ou apagado troca a versão, e a próxima tela de
# qualquer pessoa conta de novo. LEIA-ME-V10, seção 120.
def _faixa_mudou(sender, **kwargs):
    from .templatetags.rh_extras import esquecer_faixa

    esquecer_faixa()


for _modelo in (Colaborador, TermoExclusividade):
    post_save.connect(_faixa_mudou, sender=_modelo, dispatch_uid=f"rh.faixa.save.{_modelo.__name__}")
    post_delete.connect(_faixa_mudou, sender=_modelo, dispatch_uid=f"rh.faixa.delete.{_modelo.__name__}")
