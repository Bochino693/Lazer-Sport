"""Validação e duas versões WebP; nunca guarda o original pesado."""
from io import BytesIO
import uuid
import warnings

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .utils import ErroDeFormulario


def preparar_foto(arquivo):
    if arquivo.size > 5 * 1024 * 1024:
        raise ErroDeFormulario("A foto deve ter no máximo 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(arquivo) as original:
                if original.format not in ("JPEG", "PNG", "WEBP"):
                    raise ErroDeFormulario("Use uma foto JPG, PNG ou WebP.")
                if original.width * original.height > 20_000_000:
                    raise ErroDeFormulario("A foto deve ter no máximo 20 megapixels.")
                imagem = ImageOps.exif_transpose(original).convert("RGBA")
                imagem.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ErroDeFormulario("Não foi possível ler a foto. Use um JPG, PNG ou WebP válido.")
    nome = uuid.uuid4().hex
    versoes = []
    for tamanho, qualidade in ((960, 78), (160, 72)):
        copia = imagem.copy()
        copia.thumbnail((tamanho, tamanho), Image.Resampling.LANCZOS)
        dados = BytesIO()
        copia.save(dados, format="WEBP", quality=qualidade, method=4)
        versoes.append(ContentFile(dados.getvalue(), name=f"{nome}-{tamanho}.webp"))
    return versoes
