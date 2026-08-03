# core/api/serializers.py
#
# Fatia 1 -- Catálogo (somente leitura).
#
# Campos batem com os models reais de core/models.py. Onde o nome do
# campo no Django é feio pro app (nome_brinquedo, valor_brinquedo),
# renomeei no JSON pra algo limpo -- o Kotlin fica mais legível e o
# Django não precisa mudar.
#
# IMAGENS: o site já usa Cloudinary. Em vez de mandar a URL crua
# (que pode ter 800 KB), a função _url_cloudinary injeta transformações
# na URL: redimensiona, escolhe o formato (WebP/AVIF conforme o
# aparelho) e ajusta a qualidade automaticamente. O app baixa ~40 KB
# no lugar de ~800 KB. Isso é o mesmo problema que estourou a cota da
# Vercel -- resolvido na origem desta vez.

import re

from rest_framework import serializers

from core.models import (
    Brinquedos,
    CategoriasBrinquedos,
    ImagemPeca,
    PecasReposicao,
)

# Transformações padrão. w_ = largura, f_auto = formato automático,
# q_auto = qualidade automática, c_limit = não aumenta imagem pequena.
THUMB = "w_400,f_auto,q_auto,c_limit"
DETALHE = "w_900,f_auto,q_auto,c_limit"


def _url_cloudinary(campo_imagem, transformacao=THUMB):
    """Devolve a URL do Cloudinary já com transformação embutida.

    A URL do Cloudinary tem o formato:
        https://res.cloudinary.com/<cloud>/image/upload/<public_id>
    Basta inserir a transformação logo depois de /upload/.
    """
    if not campo_imagem:
        return None

    try:
        url = campo_imagem.url
    except (ValueError, AttributeError):
        return None

    if not url:
        return None

    # Se não for Cloudinary (ambiente local), devolve como está.
    if "/upload/" not in url:
        return url

    # Evita empilhar transformação em URL que já tem uma.
    if re.search(r"/upload/[a-z]{1,3}_[^/]+/", url):
        return url

    return url.replace("/upload/", f"/upload/{transformacao}/", 1)


class CategoriaSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="nome_categoria")
    imagem = serializers.SerializerMethodField()

    class Meta:
        model = CategoriasBrinquedos
        fields = ["id", "nome", "imagem"]

    def get_imagem(self, obj):
        return _url_cloudinary(obj.imagem_categoria)


class BrinquedoListaSerializer(serializers.ModelSerializer):
    """Versão enxuta -- usada na grade do catálogo.

    Não traz descrição nem dimensões de propósito: numa lista de 200
    itens isso é payload jogado fora. O app busca o resto no detalhe.
    """

    nome = serializers.CharField(source="nome_brinquedo")
    valor = serializers.DecimalField(
        source="valor_brinquedo",
        max_digits=10,
        decimal_places=2,
    )
    imagem = serializers.SerializerMethodField()

    class Meta:
        model = Brinquedos
        fields = [
            "id",
            "nome",
            "valor",
            "avaliacao",
            "imagem",
            "exibir_na_loja",
        ]

    def get_imagem(self, obj):
        return _url_cloudinary(obj.imagem_brinquedo, THUMB)


class BrinquedoDetalheSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="nome_brinquedo")
    valor = serializers.DecimalField(
        source="valor_brinquedo",
        max_digits=10,
        decimal_places=2,
    )
    imagem = serializers.SerializerMethodField()
    categorias = CategoriaSerializer(
        source="categorias_brinquedos",
        many=True,
        read_only=True,
    )
    dimensoes = serializers.SerializerMethodField()

    class Meta:
        model = Brinquedos
        fields = [
            "id",
            "nome",
            "descricao",
            "valor",
            "avaliacao",
            "voltz",
            "imagem",
            "categorias",
            "dimensoes",
            "exibir_na_loja",
        ]

    def get_imagem(self, obj):
        return _url_cloudinary(obj.imagem_brinquedo, DETALHE)

    def get_dimensoes(self, obj):
        """Agrupado num objeto só -- no app vira um data class limpo."""
        if not any([obj.altura_m, obj.largura_m, obj.profundidade_m]):
            return None
        return {
            "altura_m": obj.altura_m,
            "largura_m": obj.largura_m,
            "profundidade_m": obj.profundidade_m,
        }


class ImagemPecaSerializer(serializers.ModelSerializer):
    imagem = serializers.SerializerMethodField()

    class Meta:
        model = ImagemPeca
        fields = ["id", "posicao", "imagem"]

    def get_imagem(self, obj):
        return _url_cloudinary(obj.imagem)


class PecaSerializer(serializers.ModelSerializer):
    """Atenção: preco_fornecedor e ganho_potencial NÃO entram aqui.

    São dados internos de margem. Se vazarem no JSON, qualquer um lê
    com o navegador. Nunca adicione esses campos neste serializer.
    """

    preco = serializers.DecimalField(
        source="preco_venda",
        max_digits=9,
        decimal_places=2,
    )
    descricao = serializers.CharField(source="descricao_peca")
    imagens = ImagemPecaSerializer(
        source="imagem_peca_reposicao",
        many=True,
        read_only=True,
    )

    class Meta:
        model = PecasReposicao
        fields = ["id", "nome", "descricao", "preco", "imagens"]