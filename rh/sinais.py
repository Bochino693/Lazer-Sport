"""Apagar o documento no banco apaga o arquivo -- depois do commit.

Se a transação desfizer a exclusão, o arquivo continua lá: apagar antes do
commit deixaria uma linha apontando para um arquivo que não existe.
"""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import DocumentoColaborador


@receiver(post_delete, sender=DocumentoColaborador)
def apagar_arquivo(sender, instance, **kwargs):
    nome = instance.arquivo.name if instance.arquivo else ""
    if not nome:
        return
    armazenamento = instance.arquivo.storage
    transaction.on_commit(lambda: armazenamento.delete(nome))
