from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Prime(models.Model):
    ativo = models.BooleanField(default=True)
    criacao = models.DateTimeField(auto_now_add=True, null=True)
    atualizado = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class ClientePerfil(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil"
    )
    nome_completo = models.CharField(max_length=150, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name = "Perfil de Cliente"
        verbose_name_plural = "Perfis de Clientes"


# --- AQUI embaixo vem o signal ---

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def criar_perfil_cliente(sender, instance, created, **kwargs):
    if created:
        ClientePerfil.objects.create(user=instance)


class ImagensSite(Prime):
    imagem = models.ImageField(upload_to='imagens_site', blank=True, null=True)

    def __str__(self):
        return f'{self.imagem.url} foto'

    class Meta:
        verbose_name = "Imagem do Site"
        verbose_name_plural = "Imagens do Site"


class Clientes(Prime):
    descricao_cliente = models.CharField(max_length=120, null=True)
    logo_cliente = models.ImageField(upload_to='logo_clientes/', null=False, blank=False)

    def __str__(self):
        return self.descricao_cliente

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"


class CategoriasBrinquedos(Prime):
    imagem_categoria = models.ImageField(upload_to='categorias/', null=True, blank=False, unique=True)
    nome_categoria = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return self.nome_categoria

    class Meta:
        verbose_name = "Categoria de Produto"
        verbose_name_plural = "Categorias de Produtos"


class TagsBrinquedos(Prime):
    nome_tags = models.CharField(max_length=180)

    def __str__(self):
        return self.nome_tags

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"


class Estabelecimentos(Prime):
    nome_estabelecimento = models.CharField(max_length=180)

    def __str__(self):
        return self.nome_estabelecimento

    class Meta:
        verbose_name = "Estabelecimentos"
        verbose_name_plural = "Estabelecimentos"


def parse_metro(value):
    """
    Converte entradas como "2,19" ou "2.19" ou 2.19 para Decimal('2.19').
    Retorna None se value for None ou vazio.
    Lança InvalidOperation/ValueError se impossível converter.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None

    # Se já for Decimal or float or int — converte diretamente
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    # string: substituir vírgula por ponto, remover espaços
    if isinstance(value, str):
        normalized = value.strip().replace(",", ".")
        try:
            return Decimal(normalized)
        except InvalidOperation:
            raise InvalidOperation(f"Não foi possível converter '{value}' para Decimal.")

    # tipo não esperado
    raise ValueError("Tipo de valor inesperado para parse_metro")


class Brinquedos(Prime):
    nome_brinquedo = models.CharField(max_length=150)
    imagem_brinquedo = models.ImageField(upload_to='imagens_brinquedos', null=False)
    descricao = models.CharField(max_length=999)
    valor_brinquedo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    avaliacao = models.DecimalField(decimal_places=2, max_digits=6)

    categorias_brinquedos = models.ManyToManyField(
        CategoriasBrinquedos,
        related_name='brinquedos'
    )
    tags = models.ManyToManyField(
        TagsBrinquedos,
        related_name='brinquedos_tags'
    )

    estabelecimentos = models.ManyToManyField(
        Estabelecimentos,
        related_name='brinquedos',
        blank=True
    )

    voltz = models.CharField(max_length=10)

    # Agora considerando valores EM METROS
    altura_m = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    largura_m = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    profundidade_m = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    # Dimensões em metros
    @property
    def dimensoes_m(self):
        if self.altura_m and self.largura_m and self.profundidade_m:
            return f"{self.altura_m}m x {self.largura_m}m x {self.profundidade_m}m"
        return None

    # Volume em metros cúbicos
    @property
    def metros_cubicos(self):
        if self.altura_m and self.largura_m and self.profundidade_m:
            a = float(self.altura_m)
            l = float(self.largura_m)
            p = float(self.profundidade_m)
            return round(a * l * p, 6)
        return None

    @property
    def volume_formatado(self):
        if self.metros_cubicos is None:
            return None

        valor = self.metros_cubicos

        # Formatação humana: sem zeros inúteis, com milhar e vírgula decimal
        valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # Remove ",00" quando for número inteiro
        if valor_formatado.endswith(",00"):
            valor_formatado = valor_formatado[:-3]

        return f"{valor_formatado} m³"

    def __str__(self):
        return self.nome_brinquedo

    class Meta:
        verbose_name = "Brinquedo"
        verbose_name_plural = "Brinquedos"


class Combos(Prime):
    descricao = models.CharField(max_length=90)
    imagem_combo = models.ImageField(upload_to='combos/', null=True)
    brinquedos = models.ManyToManyField(
        Brinquedos,
        related_name='combos'
    )
    valor_combo = models.DecimalField(decimal_places=2, max_digits=10)

    def __str__(self):
        return self.descricao

    class Meta:
        verbose_name = "Combo"
        verbose_name_plural = "Combos"


class Promocoes(Prime):
    descricao = models.CharField(max_length=120)
    imagem_promocao = models.ImageField(upload_to='promocoes/', null=True)
    brinquedos = models.ForeignKey(Brinquedos, related_name='promocoes', on_delete=models.CASCADE)
    preco_promocao = models.DecimalField(decimal_places=2, max_digits=10, null=True)

    def __str__(self):
        return self.descricao

    class Meta:
        verbose_name = "Promoção"
        verbose_name_plural = "Promoções"


class Cupom(Prime):
    codigo = models.CharField(max_length=12)
    desconto_percentual = models.DecimalField(decimal_places=2, max_digits=10)

    def __str__(self):
        return self.codigo

    class Meta:
        verbose_name = "Cupom de Desconto"
        verbose_name_plural = "Cupons de Desconto"


class BrinquedosProjeto(Prime):
    nome_brinquedo_projeto = models.CharField(max_length=150)
    descricao = models.CharField(max_length=999)

    def __str__(self):
        return self.nome_brinquedo_projeto

    class Meta:
        verbose_name = "Brinquedo Projetado"
        verbose_name_plural = "Brinquedos Projetados"


class ImagemProjetoBrinquedo(Prime):
    brinquedo = models.ForeignKey(
        BrinquedosProjeto,
        on_delete=models.CASCADE,
        related_name='imagens_brinquedo_projeto'
    )
    imagem = models.ImageField(upload_to='projetos/')
    legenda = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Imagem de {self.brinquedo.nome_brinquedo_projeto}"

    class Meta:
        verbose_name = "Imagem do Brinquedo Projetado"
        verbose_name_plural = "Imagens dos Brinquedos Projetados"


class Projetos(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    brinquedo_projetado = models.OneToOneField(
        BrinquedosProjeto,
        related_name='projeto',
        on_delete=models.CASCADE,
        null=True
    )

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"


class Eventos(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    brinquedos = models.ManyToManyField(
        Brinquedos,
        related_name='eventos_brinquedos'
    )

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"


class ImagemEvento(models.Model):
    evento = models.ForeignKey(  # ✔ CORRETO AGORA
        Eventos,
        on_delete=models.CASCADE,
        related_name='imagens_evento',
        null=True

    )
    imagem = models.ImageField(upload_to='eventos/')
    legenda = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Imagem de {self.evento.titulo}"

    class Meta:
        verbose_name = "Imagem do Evento"
        verbose_name_plural = "Imagens dos Eventos"


class BrinquedoSobMedida(models.Model):
    brinquedo_original = models.ForeignKey(Brinquedos, on_delete=models.CASCADE)
    altura = models.DecimalField(max_digits=10, decimal_places=2)
    largura = models.DecimalField(max_digits=10, decimal_places=2)
    profundidade = models.DecimalField(max_digits=10, decimal_places=2)
    valor_calculado = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.brinquedo_original.nome_brinquedo

    class Meta:
        verbose_name = "Brinquedo Sob Medida"
        verbose_name_plural = "Brinquedos Sob Medida"


class Carrinho(Prime):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carrinho', null=True)

    cupom = models.ForeignKey(
        Cupom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carrinhos'
    )

    # TOTAL BRUTO = soma dos itens SEM desconto
    @property
    def total_bruto(self):
        return round(sum(item.subtotal for item in self.itens.all()), 2)

    # VALOR DO CUPOM (se houver)
    @property
    def valor_desconto(self):
        if not self.cupom:
            return 0

        desconto = (self.total_bruto * float(self.cupom.desconto_percentual)) / 100
        return round(desconto, 2)

    # TOTAL FINAL = total_bruto - desconto
    @property
    def total_liquido(self):
        return round(self.total_bruto - self.valor_desconto, 2)

    def __str__(self):
        return f"Carrinho de {self.usuario.username}"


class ItemCarrinho(Prime):
    carrinho = models.ForeignKey(Carrinho, on_delete=models.CASCADE, related_name='itens')

    # Generic ForeignKey
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    item = GenericForeignKey('content_type', 'object_id')

    quantidade = models.PositiveIntegerField(default=1)

    @property
    def preco_unitario(self):
        # Brinquedo
        if hasattr(self.item, 'valor_brinquedo'):
            return self.item.valor_brinquedo

        # Combo
        if hasattr(self.item, 'valor_combo'):
            return self.item.valor_combo

        # Promoção
        if hasattr(self.item, 'preco_promocao'):
            return self.item.preco_promocao

        return 0

    @property
    def subtotal(self):
        return round(self.preco_unitario * self.quantidade, 2)

    def __str__(self):
        return f"Item {self.item} (x{self.quantidade})"


class Venda(Prime):
    carrinho = models.ForeignKey(Carrinho, on_delete=models.SET_NULL, related_name='vendas', null=True)
