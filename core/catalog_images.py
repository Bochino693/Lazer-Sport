"""Compatibilidade entre as imagens antigas e as galerias do catálogo."""

from django.db import transaction
from django.db.models import F

from .models import Brinquedos, ImagemBrinquedo, ImagemPeca, PecasReposicao


def adicionar_imagens_atuais_como_primeira(brinquedos=None):
    """Copia a imagem única de cada brinquedo para a posição 1 da galeria.

    A função não duplica registros e não substitui uma foto principal que já
    tenha sido configurada na galeria.
    """
    queryset = brinquedos
    if queryset is None:
        queryset = (
            Brinquedos.objects
            .exclude(imagem_brinquedo__isnull=True)
            .exclude(imagem_brinquedo="")
        )

    criadas = 0
    for brinquedo in queryset.iterator():
        if ImagemBrinquedo.objects.filter(
            brinquedo=brinquedo,
            ordem=1,
        ).exists():
            continue

        ImagemBrinquedo.objects.create(
            brinquedo=brinquedo,
            imagem=brinquedo.imagem_brinquedo.name,
            ordem=1,
            texto_alternativo=(
                f"Foto principal de {brinquedo.nome_brinquedo}"[:180]
            ),
        )
        criadas += 1
    return criadas


def numerar_imagens_existentes_das_pecas(pecas=None):
    """Numera galerias antigas, mantendo a foto de frente como a primeira."""
    queryset = pecas
    if queryset is None:
        queryset = PecasReposicao.objects.prefetch_related(
            "imagem_peca_reposicao"
        )

    atualizadas = 0
    for peca in queryset.iterator(chunk_size=500):
        imagens = list(peca.imagem_peca_reposicao.all())
        ordens_atuais = [imagem.ordem for imagem in imagens]
        frente = next((
            imagem for imagem in imagens
            if imagem.posicao == ImagemPeca.PosicaoImagem.FRENTE
        ), None)
        galeria_ja_preparada = (
            ordens_atuais == list(range(1, len(imagens) + 1))
            and (frente is None or (imagens and imagens[0].pk == frente.pk))
        )
        if galeria_ja_preparada:
            continue

        imagens.sort(
            key=lambda imagem: (
                imagem.posicao != ImagemPeca.PosicaoImagem.FRENTE,
                imagem.id,
            )
        )
        ImagemPeca.objects.filter(peca_reposicao=peca).update(
            ordem=F("ordem") + 100
        )
        for ordem, imagem in enumerate(imagens, start=1):
            ImagemPeca.objects.filter(pk=imagem.pk).update(ordem=ordem)
            atualizadas += 1
    return atualizadas


@transaction.atomic
def preparar_galerias_catalogo():
    """Prepara brinquedos e peças e retorna um resumo da operação."""
    return {
        "fotos_brinquedos_criadas": adicionar_imagens_atuais_como_primeira(),
        "fotos_pecas_numeradas": numerar_imagens_existentes_das_pecas(),
    }
