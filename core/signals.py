# core/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import ClientePerfil

@receiver(post_save, sender=User)
def criar_perfil_cliente(sender, instance, created, **kwargs):
    if created:
        ClientePerfil.objects.get_or_create(user=instance)
