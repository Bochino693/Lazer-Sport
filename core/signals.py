# core/signals.py
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in

from .context_processors import limpar_cache_global
from .home_cache import invalidate_public_catalog_caches
from .models import (
    Brinquedos,
    BrinquedosProjeto,
    CategoriaPeca,
    CategoriasBrinquedos,
    ClientePerfil,
    Combos,
    EnderecoEmpresa,
    Estabelecimentos,
    Eventos,
    ImagemBrinquedo,
    ImagemEvento,
    ImagemPeca,
    ImagemProjetoBrinquedo,
    ImagensSite,
    Pedido,
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


@receiver(post_save, sender=Pedido, dispatch_uid="core.pedido.avisar_superusuarios")
def avisar_superusuarios_de_novo_pedido(sender, instance, created, **kwargs):
    """O pedido só dispara depois do commit; rollback nunca gera alarme falso."""
    if not created:
        return
    pedido_id = instance.pk

    def avisar():
        from sistema_interno.notificacoes import avisar_novo_pedido_id

        avisar_novo_pedido_id(pedido_id)

    transaction.on_commit(avisar)


def _invalidar_home(sender, **kwargs):
    transaction.on_commit(invalidate_public_catalog_caches)


def _invalidar_home_m2m(sender, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        transaction.on_commit(invalidate_public_catalog_caches)


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


# O cliente vive no app do painel; a vitrine só o lê. Importado aqui
# dentro -- e não no topo -- porque este módulo é carregado no `ready()` do
# core, e nesse instante o app do painel ainda pode não ter modelos
# prontos.
from sistema_interno.models import Cliente as _ClienteDoPainel  # noqa: E402

for _modelo in (CategoriasBrinquedos, Estabelecimentos, _ClienteDoPainel):
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


# ------------------------------------------------------------------
# Curtidas e lista de desejos
# ------------------------------------------------------------------

@receiver(user_logged_in)
def adotar_favoritos_do_dispositivo(sender, request, user, **kwargs):
    """O que a pessoa curtiu antes de entrar não pode sumir no login."""
    if request is None:
        return

    from .favoritos import chave_dispositivo, migrar_dispositivo_para_conta

    migrar_dispositivo_para_conta(user, chave_dispositivo(request))
