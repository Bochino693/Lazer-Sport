"""Validação e gravação das fotos dos cadastros dentro de documentos."""
from django import forms
from django.core.exceptions import ValidationError
from core.models import ImagemBrinquedo, ImagemPeca
from .utils import ErroDeFormulario


def validar(request, *, brinquedo=False):
    posicoes = ImagemBrinquedo.TIPO_CHOICES if brinquedo else ImagemPeca.PosicaoImagem.choices
    fotos = []
    for posicao, rotulo in posicoes:
        arquivo = request.FILES.get("foto_" + posicao)
        if not arquivo:
            continue
        if arquivo.size > 5 * 1024 * 1024:
            raise ErroDeFormulario(f"Foto {rotulo}: use uma imagem de até 5 MB.")
        try:
            arquivo = forms.ImageField().clean(arquivo)
        except ValidationError as exc:
            raise ErroDeFormulario(f"Foto {rotulo}: o arquivo não é uma imagem válida.") from exc
        fotos.append((posicao, arquivo))
    if sum(f.size for _, f in fotos) > 16 * 1024 * 1024:
        raise ErroDeFormulario("As fotos juntas devem ter até 16 MB.")
    return fotos


def salvar(objeto, fotos, *, brinquedo=False):
    gravadas = []
    try:
        for ordem, (posicao, arquivo) in enumerate(fotos, 1):
            if brinquedo:
                registro = ImagemBrinquedo(
                    brinquedo=objeto, tipo=posicao, ordem=ordem, imagem=arquivo,
                    texto_alternativo=f"{objeto.nome_brinquedo} — {posicao}"[:180],
                )
            else:
                registro = ImagemPeca(
                    peca_reposicao=objeto, posicao=posicao, ordem=ordem, imagem=arquivo,
                )
            gravadas.append(registro)
            registro.save()
            if brinquedo and posicao == ImagemBrinquedo.TIPO_PERFIL:
                objeto.imagem_brinquedo = registro.imagem.name
                objeto.save(update_fields=["imagem_brinquedo"])

    except Exception as exc:
        # Arquivos são externos à transação SQL: compensar apenas uploads desta chamada.
        for registro in gravadas:
            if registro.imagem and registro.imagem._committed:
                try:
                    registro.imagem.delete(save=False)
                except Exception:
                    import logging
                    logging.getLogger(__name__).warning("Falha ao limpar upload incompleto de catálogo")
        raise ErroDeFormulario("Não foi possível guardar todas as fotos. O item não foi cadastrado; mantenha a janela aberta e tente novamente.") from exc
