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
    ComponenteBrinquedo,
    EnderecoEmpresa,
    Estabelecimentos,
    Eventos,
    ImagemBrinquedo,
    ImagemEvento,
    ImagemPeca,
    ImagemProjetoBrinquedo,
    ImagensSite,
    JogoCadastrado,
    ObjetoTresD,
    ObjetoTresDProjeto,
    Pedido,
    VarianteAdesivo,
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


@receiver(post_save, sender=User, dispatch_uid="core.user.registrar_cadastro")
def registrar_cadastro_do_usuario(sender, instance, created, raw=False, **kwargs):
    """De onde veio a conta (IP, navegador, caminho): ver core/registro_cadastro.py.

    Um só gancho para os três caminhos que criam conta. Nunca levanta:
    um defeito no registro não pode impedir ninguém de se cadastrar.
    """
    if created and not raw:
        from .registro_cadastro import registrar

        registrar(instance)


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


@receiver(post_save, sender=Pedido, dispatch_uid="core.pedido.acertar_venda")
def acertar_venda_do_pedido(sender, instance, created, raw=False, update_fields=None, **kwargs):
    """O pedido pago vira venda; o cancelado deixa de ser (LEIA-ME-V10, 89).

    POR QUE UM SINAL. O pagamento aprovado é gravado pelo checkout
    (`core.checkout.confirmar_pagamento`), e o checkout não é lugar de
    regra de venda: o que importa lá é o dinheiro do cliente. O sinal
    ouve a mudança de SITUAÇÃO do pedido, venha de onde vier -- checkout,
    painel, admin --, e acerta a venda depois do commit:

      * depois do commit, e não dentro: a confirmação do pagamento nunca
        falha nem fica mais lenta por causa da venda;
      * `robust`: se o acerto der erro, ele vai para o log e o resto
        segue -- o painel e a migração acertam de novo, e acertar duas
        vezes não duplica (`Pedido.acertar_venda`).

    Só mudança de situação interessa: o `save` que grava "impresso" ou o
    prazo de produção não chega a consultar nada.
    """
    if raw:
        return
    if update_fields is not None and "status" not in update_fields:
        return
    # O pedido nasce aguardando pagamento (a reserva do checkout): ainda
    # não há venda a acertar, e o pedido novo não paga uma consulta a mais.
    if created and instance.status not in Pedido.SITUACOES_PAGAS:
        return
    pedido_id = instance.pk

    def acertar():
        Pedido.acertar_venda_do_pedido(pedido_id)

    transaction.on_commit(acertar, robust=True)


def _invalidar_home(sender, **kwargs):
    # NA HORA e DEPOIS DO COMMIT, de propósito. Na hora: dentro da mesma
    # transação (o painel grava o brinquedo e as fotos em um bloco só), a
    # próxima leitura já não encontra a cópia velha -- e os testes, que
    # nunca fazem commit, também não. No commit: uma requisição concorrente
    # pode ter reconstruído o cache no meio da gravação, com o dado ainda
    # não gravado; a segunda invalidação apaga essa cópia. Apagar duas vezes
    # custa nada; servir o cadastro velho custa uma venda.
    invalidate_public_catalog_caches()
    transaction.on_commit(invalidate_public_catalog_caches)
    # as fotos que giram nos cards (core/fotos_dos_cards.py): saem das fotos e dos brinquedos
    from .fotos_dos_cards import limpar_cache

    limpar_cache()
    transaction.on_commit(limpar_cache)


def _invalidar_home_m2m(sender, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        invalidate_public_catalog_caches()
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
    # As telas do catálogo em cache (core/home_cache.py) também mostram o
    # objeto 3D da ficha do brinquedo e os jogos cadastrados do simulador.
    ObjetoTresD,
    # a ficha do projeto mostra o 3D dele e o produto da loja (o paralelo)
    ObjetoTresDProjeto,
    JogoCadastrado,
    # a página do brinquedo mostra o que vem dentro dele e de que conjunto faz parte
    ComponenteBrinquedo,
    # os adesivos do produto (a página e os cards)
    VarianteAdesivo,
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
    Promocoes.brinquedos_extras.through,
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


@receiver(user_logged_in)
def adotar_partidas_dos_jogos(sender, request, user, **kwargs):
    """A partida grátis jogada antes de entrar vai para o ranking."""
    if request is None or not hasattr(request, "session"):
        return

    from .ranking import adotar_partidas_da_sessao

    adotar_partidas_da_sessao(request, user)


# O mapa é parte do contexto público cacheado: refletir cadastro, local e proposta.
from sistema_interno.models import EnderecoCliente as _EnderecoDoCliente, Orcamento as _PropostaDoCliente
for _modelo in (_ClienteDoPainel, _EnderecoDoCliente, _PropostaDoCliente):
    for _sinal, _evento in ((post_save, "save"), (post_delete, "delete")):
        _sinal.connect(_invalidar_home, sender=_modelo, weak=False,
                       dispatch_uid=f"core.mapa.{_evento}.{_modelo._meta.label_lower}")



# O portal de jogos guarda os anúncios no ar num cache curto (core/portal_jogos.py):
# anúncio salvo ou apagado no /system/ aparece (ou some) na hora.
def _anuncio_mudou(sender, **kwargs):
    from .portal_jogos import esquecer_vivo

    esquecer_vivo()


def _ligar_anuncios():
    from .models import AnuncioJogos

    post_save.connect(_anuncio_mudou, sender=AnuncioJogos, dispatch_uid="core.anuncio_jogos.save")
    post_delete.connect(_anuncio_mudou, sender=AnuncioJogos, dispatch_uid="core.anuncio_jogos.delete")


_ligar_anuncios()
