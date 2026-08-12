# core/signals.py
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from .context_processors import limpar_cache_global
from .home_cache import invalidate_home_cache
from .models import (
    Brinquedos,
    BrinquedosProjeto,
    CategoriaPeca,
    CategoriasBrinquedos,
    ClientePerfil,
    Clientes,
    Combos,
    EnderecoEmpresa,
    Estabelecimentos,
    Eventos,
    ImagemBrinquedo,
    ImagemEvento,
    ImagemPeca,
    ImagemProjetoBrinquedo,
    ImagensSite,
    PecasReposicao,
    Projetos,
    Promocoes,
    TagsBrinquedos,
)

@receiver(post_save, sender=User)
def criar_perfil_cliente(sender, instance, created, **kwargs):
    if created:
        # cria perfil com telefone vazio (ou default)
        ClientePerfil.objects.get_or_create(user=instance, defaults={'telefone': ''})


def _invalidar_home(sender, **kwargs):
    transaction.on_commit(invalidate_home_cache)


def _invalidar_home_m2m(sender, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        transaction.on_commit(invalidate_home_cache)


_MODELOS_DA_HOME = (
    Brinquedos,
    ImagemBrinquedo,
    CategoriasBrinquedos,
    TagsBrinquedos,
    Estabelecimentos,
    PecasReposicao,
    ImagemPeca,
    CategoriaPeca,
    Combos,
    Promocoes,
    Eventos,
    ImagemEvento,
    Projetos,
    BrinquedosProjeto,
    ImagemProjetoBrinquedo,
    ImagensSite,
    Clientes,
    EnderecoEmpresa,
)

for _modelo in _MODELOS_DA_HOME:
    _identificador = _modelo._meta.label_lower
    post_save.connect(
        _invalidar_home,
        sender=_modelo,
        weak=False,
        dispatch_uid=f"core.home.post_save.{_identificador}",
    )
    post_delete.connect(
        _invalidar_home,
        sender=_modelo,
        weak=False,
        dispatch_uid=f"core.home.post_delete.{_identificador}",
    )


_RELACOES_DA_HOME = (
    Brinquedos.categorias_brinquedos.through,
    Brinquedos.tags.through,
    Brinquedos.estabelecimentos.through,
    PecasReposicao.categoria_peca.through,
    Combos.brinquedos.through,
    Eventos.brinquedos.through,
)

for _relacao in _RELACOES_DA_HOME:
    m2m_changed.connect(
        _invalidar_home_m2m,
        sender=_relacao,
        weak=False,
        dispatch_uid=f"core.home.m2m.{_relacao._meta.label_lower}",
    )


def _invalidar_contexto_global(sender, **kwargs):
    transaction.on_commit(limpar_cache_global)


for _modelo in (CategoriasBrinquedos, Estabelecimentos, Clientes):
    _identificador = _modelo._meta.label_lower
    post_save.connect(
        _invalidar_contexto_global,
        sender=_modelo,
        weak=False,
        dispatch_uid=f"core.contexto.post_save.{_identificador}",
    )
    post_delete.connect(
        _invalidar_contexto_global,
        sender=_modelo,
        weak=False,
        dispatch_uid=f"core.contexto.post_delete.{_identificador}",
    )
