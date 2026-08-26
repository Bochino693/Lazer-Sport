# core/api/serializer.py
#
# CORREÇÕES DESTA VERSÃO:
#   - get_dimensoes devolvia Decimal cru -> o JSON saía número e o app
#     (que espera string) quebrava. Agora sai string sempre.
#   - a lista de brinquedos mandava a URL crua do Cloudinary (~800 KB
#     por imagem). Agora usa THUMB, igual ao resto.
#   - novos serializers: estabelecimentos, eventos, combos, promoções,
#     manutenções e pedidos.
#
# REGRA GERAL: todo campo numérico que o app lê como texto sai como
# string. Misturar tipo entre versões da API é o que derruba cliente
# tipado.

import re

from rest_framework import serializers

from core.models import (
    Brinquedos,
    CategoriasBrinquedos,
    Combos,
    Estabelecimentos,
    Eventos,
    ImagemEvento,
    ImagemPeca,
    ItemPedido,
    Manutencao,
    PecasReposicao,
    Pedido,
    Promocoes,
)

THUMB = "w_400,f_auto,q_auto,c_limit"
DETALHE = "w_900,f_auto,q_auto,c_limit"
LARGO = "w_800,h_500,c_fill,f_auto,q_auto"


def _url_cloudinary(campo_imagem, transformacao=THUMB):
    """URL do Cloudinary já com transformação embutida."""
    if not campo_imagem:
        return None

    try:
        url = campo_imagem.url
    except (ValueError, AttributeError):
        return None

    if not url:
        return None

    if "/upload/" not in url:
        return url

    if re.search(r"/upload/[a-z]{1,3}_[^/]+/", url):
        return url

    return url.replace("/upload/", f"/upload/{transformacao}/", 1)


def _texto(valor):
    """Decimal/float/None -> string ou None. Nunca número solto."""
    if valor is None:
        return None
    return str(valor)


# ============================================================
# CATÁLOGO
# ============================================================

def _curtidas(obj):
    """Curtidas do produto.

    Usa a anotação ``total_curtidas`` quando a view já trouxe o número na
    mesma consulta -- sem ela, listagem viraria uma consulta por item.
    """
    total = getattr(obj, "total_curtidas", None)
    if total is not None:
        return total
    return obj.favoritos.filter(tipo="curtida").count()


class CategoriaSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="nome_categoria")
    imagem = serializers.SerializerMethodField()

    class Meta:
        model = CategoriasBrinquedos
        fields = ["id", "nome", "imagem"]

    def get_imagem(self, obj):
        return _url_cloudinary(obj.imagem_categoria)


class BrinquedoListaSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="nome_brinquedo")
    valor = serializers.SerializerMethodField()
    avaliacao = serializers.SerializerMethodField()
    imagem = serializers.SerializerMethodField()
    curtidas = serializers.SerializerMethodField()

    class Meta:
        model = Brinquedos
        fields = (
            "id",
            "nome",
            "valor",
            "avaliacao",
            "imagem",
            "exibir_na_loja",
            "curtidas",
        )

    def get_curtidas(self, obj):
        return _curtidas(obj)

    def get_valor(self, obj):
        return _texto(obj.valor_brinquedo)

    def get_avaliacao(self, obj):
        return _texto(obj.avaliacao)

    # BrinquedoListaSerializer.get_imagem
    def get_imagem(self, obj):
        return _url_cloudinary(obj.imagem_catalogo, THUMB)


class BrinquedoDetalheSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="nome_brinquedo")
    valor = serializers.SerializerMethodField()
    avaliacao = serializers.SerializerMethodField()
    imagem = serializers.SerializerMethodField()
    categorias = CategoriaSerializer(
        source="categorias_brinquedos",
        many=True,
        read_only=True,
    )
    dimensoes = serializers.SerializerMethodField()
    curtidas = serializers.SerializerMethodField()

    def get_curtidas(self, obj):
        return _curtidas(obj)

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
            "curtidas",
        ]

    def get_valor(self, obj):
        return _texto(obj.valor_brinquedo)

    def get_avaliacao(self, obj):
        return _texto(obj.avaliacao)

    # BrinquedoDetalheSerializer.get_imagem
    def get_imagem(self, obj):
        return _url_cloudinary(obj.imagem_catalogo, DETALHE)

    def get_dimensoes(self, obj):
        """AQUI ESTAVA O BUG: devolvia Decimal, virava número no JSON."""
        if not any([obj.altura_m, obj.largura_m, obj.profundidade_m]):
            return None
        return {
            "altura_m": _texto(obj.altura_m),
            "largura_m": _texto(obj.largura_m),
            "profundidade_m": _texto(obj.profundidade_m),
        }


class ImagemPecaSerializer(serializers.ModelSerializer):
    imagem = serializers.SerializerMethodField()

    class Meta:
        model = ImagemPeca
        fields = ["id", "posicao", "imagem"]

    def get_imagem(self, obj):
        return _url_cloudinary(obj.imagem)


class PecaSerializer(serializers.ModelSerializer):
    """preco_fornecedor e ganho_potencial NUNCA entram aqui."""

    preco = serializers.SerializerMethodField()
    descricao = serializers.CharField(source="descricao_peca", allow_null=True)
    imagens = ImagemPecaSerializer(
        source="imagem_peca_reposicao",
        many=True,
        read_only=True,
    )
    curtidas = serializers.SerializerMethodField()

    class Meta:
        model = PecasReposicao
        fields = ["id", "nome", "descricao", "preco", "imagens", "curtidas"]

    def get_curtidas(self, obj):
        return _curtidas(obj)

    def get_preco(self, obj):
        return _texto(obj.preco_venda)


# ============================================================
# INSTITUCIONAL
# ============================================================

class EstabelecimentoSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="nome_estabelecimento")
    imagem = serializers.SerializerMethodField()

    class Meta:
        model = Estabelecimentos
        fields = ["id", "nome", "imagem"]

    def get_imagem(self, obj):
        return _url_cloudinary(obj.imagem_estabelecimento, LARGO)


class ImagemEventoSerializer(serializers.ModelSerializer):
    imagem = serializers.SerializerMethodField()

    class Meta:
        model = ImagemEvento
        fields = ["imagem", "legenda"]

    def get_imagem(self, obj):
        return _url_cloudinary(obj.imagem, LARGO)


class EventoSerializer(serializers.ModelSerializer):
    imagens = ImagemEventoSerializer(
        source="imagens_evento",
        many=True,
        read_only=True,
    )

    class Meta:
        model = Eventos
        fields = ["id", "titulo", "descricao", "imagens"]


class ComboSerializer(serializers.ModelSerializer):
    valor = serializers.SerializerMethodField()
    imagem = serializers.SerializerMethodField()

    class Meta:
        model = Combos
        fields = ["id", "descricao", "imagem", "valor"]

    def get_valor(self, obj):
        return _texto(obj.valor_combo)

    def get_imagem(self, obj):
        return _url_cloudinary(obj.imagem_combo, THUMB)


class PromocaoSerializer(serializers.ModelSerializer):
    preco = serializers.SerializerMethodField()
    imagem = serializers.SerializerMethodField()
    brinquedo_id = serializers.IntegerField(source="brinquedos_id", read_only=True)

    class Meta:
        model = Promocoes
        fields = ["id", "descricao", "imagem", "preco", "brinquedo_id"]

    def get_preco(self, obj):
        return _texto(obj.preco_promocao)

    # PromocaoSerializer.get_imagem
    def get_imagem(self, obj):
        return (
                _url_cloudinary(obj.imagem_promocao, THUMB)
                or _url_cloudinary(
            getattr(obj.brinquedos, "imagem_catalogo", None),
            THUMB,
        )
        )


# ============================================================
# MANUTENÇÕES
# ============================================================

class ManutencaoLeituraSerializer(serializers.ModelSerializer):
    nome_equipamento = serializers.CharField(read_only=True)
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Manutencao
        fields = [
            "id",
            "nome_equipamento",
            "descricao",
            "status",
            "status_display",
            "criado_em",
            "cidade",
            "estado",
        ]


class ManutencaoEscritaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manutencao
        fields = [
            "brinquedo",
            "brinquedo_nao_listado",
            "brinquedo_descricao_livre",
            "descricao",
            "telefone_contato",
            "cep",
            "endereco",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
        ]

    def validate(self, dados):
        nao_listado = dados.get("brinquedo_nao_listado", False)
        brinquedo = dados.get("brinquedo")
        livre = (dados.get("brinquedo_descricao_livre") or "").strip()

        if nao_listado and not livre:
            raise serializers.ValidationError(
                {"brinquedo_descricao_livre": "Descreva qual é o equipamento."}
            )
        if not nao_listado and not brinquedo:
            raise serializers.ValidationError(
                {"brinquedo": "Escolha o brinquedo ou marque 'não listado'."}
            )
        if not (dados.get("descricao") or "").strip():
            raise serializers.ValidationError(
                {"descricao": "Conte o que está acontecendo."}
            )
        if not (dados.get("telefone_contato") or "").strip():
            raise serializers.ValidationError(
                {"telefone_contato": "Informe um telefone para contato."}
            )
        return dados


# ============================================================
# PEDIDOS
# ============================================================

class ItemPedidoSerializer(serializers.ModelSerializer):
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = ItemPedido
        fields = ["id", "nome_item", "tipo_item", "quantidade", "subtotal"]

    def get_subtotal(self, obj):
        return _texto(obj.subtotal)


class PedidoSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    total_final = serializers.SerializerMethodField()
    criado_em = serializers.DateTimeField(source="criacao", read_only=True)
    itens = ItemPedidoSerializer(many=True, read_only=True)

    class Meta:
        model = Pedido
        fields = [
            "id",
            "status",
            "status_display",
            "tipo_envio",
            "total_final",
            "criado_em",
            "itens",
        ]

    def get_total_final(self, obj):
        return _texto(obj.total_final)