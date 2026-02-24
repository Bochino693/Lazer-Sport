from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import requests


class Prime(models.Model):
    ativo = models.BooleanField(default=True)
    criacao = models.DateTimeField(auto_now_add=True, null=True)
    atualizado = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class EnderecoEmpresa(Prime):
    nome = models.CharField(max_length=100, default="Fabrica do Pery")

    telefone = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )

    cep = models.CharField(max_length=9)
    rua = models.CharField(max_length=255)
    numero = models.CharField(max_length=20)
    complemento = models.CharField(max_length=255, blank=True, null=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)

    latitude = models.DecimalField(
        max_digits=50, decimal_places=30, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=50, decimal_places=30, null=True, blank=True
    )

    def __str__(self):
        return f"{self.nome} - {self.cidade}/{self.estado}"


from django.db import models
from django.db.models import F, UniqueConstraint
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


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

    def clean(self):
        if ClientePerfil.objects.filter(user__username=self.user.username, user__email=self.user.email).exclude(
                pk=self.pk).exists():
            raise ValidationError("Já existe um perfil com esse usuário e email.")

    class Meta:
        verbose_name = "Perfil de Cliente"
        verbose_name_plural = "Perfis de Clientes"
        constraints = [
            UniqueConstraint(
                fields=['user'],  # garante que cada user só tenha 1 perfil
                name='unique_user_perfil'
            ),
        ]


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
        return f'Imagem {self.id}'

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
    imagem_estabelecimento = models.ImageField(upload_to='estabelecimentos/', null=True, blank=True)

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
    imagem_brinquedo = models.ImageField(upload_to='imagens_brinquedos', blank=True, null=True)
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


class CategoriaPeca(Prime):
    nome_categoria_peca = models.CharField(max_length=90)

    def __str__(self):
        return self.nome_categoria_peca

    class Meta:
        verbose_name = "Categoria de Peça"
        verbose_name_plural = "Categorias de Peças"


class PecasReposicao(Prime):
    nome = models.CharField(max_length=120)
    categoria_peca = models.ForeignKey(CategoriaPeca, on_delete=models.CASCADE, related_name='peca', null=True)
    preco_venda = models.DecimalField(decimal_places=2, max_digits=9, null=True, blank=True)
    preco_fornecedor = models.DecimalField(decimal_places=2, max_digits=9, null=True, blank=True)
    descricao_peca = models.CharField(max_length=210)

    # ⭐ novo campo
    ganho_potencial = models.DecimalField(
        decimal_places=2,
        max_digits=9,
        null=True,
        blank=True,
        editable=False
    )

    class Meta:
        verbose_name = "Peça de Reposição"
        verbose_name_plural = "Peças de Reposição"

    def __str__(self):
        return self.nome

    # ⭐ helper profissional (mantido)
    @property
    def imagem_principal(self):
        img = self.imagem_peca_reposicao.filter(
            posicao=ImagemPeca.PosicaoImagem.FRENTE
        ).first()

        if img:
            return img

        return self.imagem_peca_reposicao.first()

    # 🚀 SAVE INTELIGENTE
    def save(self, *args, **kwargs):
        # ✅ se tem fornecedor e NÃO tem venda → calcula venda automática
        if self.preco_fornecedor and not self.preco_venda:
            self.preco_venda = (
                    self.preco_fornecedor * Decimal("1.12")
            ).quantize(Decimal("0.01"))

        # ✅ calcula ganho potencial se ambos existirem
        if self.preco_venda and self.preco_fornecedor:
            self.ganho_potencial = (
                    self.preco_venda - self.preco_fornecedor
            ).quantize(Decimal("0.01"))
        else:
            self.ganho_potencial = None

        super().save(*args, **kwargs)


class ImagemPeca(Prime):
    class PosicaoImagem(models.TextChoices):
        FRENTE = "frente", "Frente"
        LADO_DIREITO = "lado_direito", "Lado direito"
        LADO_ESQUERDO = "lado_esquerdo", "Lado esquerdo"
        TRAS = "tras", "Traseira"
        DETALHE = "detalhe", "Detalhe"
        OUTRO = "outro", "Outro"

    posicao = models.CharField(
        max_length=20,
        choices=PosicaoImagem.choices,
        default=PosicaoImagem.FRENTE,
        verbose_name="Posição da imagem",
        db_index=True,
    )

    imagem = models.ImageField(
        upload_to="pecas_reposicao/",
        verbose_name="Imagem",
        null=True
    )

    peca_reposicao = models.ForeignKey(
        PecasReposicao,
        on_delete=models.CASCADE,
        related_name="imagem_peca_reposicao",
        verbose_name="Peça"
    )

    class Meta:
        verbose_name = "Imagem de Peça de Reposição"
        verbose_name_plural = "Imagens de Peças de Reposição"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["peca_reposicao"]),
        ]

    def __str__(self):
        return f" ({self.get_posicao_display()})"

    # 🚨 VALIDAÇÃO: máximo 3 imagens por peça
    def clean(self):
        if self.peca_reposicao_id:
            qs = ImagemPeca.objects.filter(
                peca_reposicao=self.peca_reposicao
            )

            # se estiver editando, exclui a própria instância
            if self.pk:
                qs = qs.exclude(pk=self.pk)

            if qs.count() >= 3:
                raise ValidationError(
                    "Cada peça pode ter no máximo 3 imagens."
                )


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
    brinquedo = models.ForeignKey(Brinquedos, on_delete=models.CASCADE, related_name='cupom', null=True)
    categoria = models.ForeignKey(CategoriasBrinquedos, on_delete=models.CASCADE, related_name='categoria', null=True)
    cliente = models.ManyToManyField(ClientePerfil, related_name='cupons')
    quantidade_uso = models.IntegerField(default=1, null=True)

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
    cliente = models.ForeignKey(
        ClientePerfil,
        on_delete=models.CASCADE,
        related_name='carrinhos',
        null=True
    )

    cupom = models.ForeignKey(
        Cupom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carrinhos'
    )

    from decimal import Decimal

    @property
    def total_bruto(self):
        total = sum(
            (item.subtotal for item in self.itens.all()),
            Decimal('0.00')
        )
        return total.quantize(Decimal('0.01'))

    @property
    def valor_desconto(self):
        if not self.cupom:
            return Decimal('0.00')

        percentual = self.cupom.desconto_percentual  # ex: Decimal('10.00')
        desconto = (self.total_bruto * percentual) / Decimal('100')

        return desconto.quantize(Decimal('0.01'))

    @property
    def total_liquido(self):
        return (self.total_bruto - self.valor_desconto).quantize(Decimal('0.01'))

    def __str__(self):
        return f"Carrinho de {self.cliente.user.username}"


class ItemCarrinho(Prime):
    carrinho = models.ForeignKey(
        Carrinho,
        on_delete=models.CASCADE,
        related_name='itens'
    )

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    item = GenericForeignKey('content_type', 'object_id')

    quantidade = models.PositiveIntegerField(default=1)

    @property
    def preco_unitario(self):
        if hasattr(self.item, 'valor_brinquedo'):
            return self.item.valor_brinquedo

        if hasattr(self.item, 'valor_combo'):
            return self.item.valor_combo

        if hasattr(self.item, 'preco_promocao'):
            return self.item.preco_promocao

        return 0

    @property
    def subtotal(self):
        return round(self.preco_unitario * self.quantidade, 2)

    def __str__(self):
        return f"Item {self.item} (x{self.quantidade})"


from django.db import transaction


class Pedido(Prime):
    STATUS_CHOICES = (
        ('criado', 'Criado'),
        ('aguardando_pagamento', 'Aguardando pagamento'),
        ('pago', 'Pago'),
        ('em_preparacao', 'Em preparação'),
        ('saiu_entrega', 'Saiu para entrega'),
        ('finalizado', 'Finalizado'),
        ('cancelado', 'Cancelado'),
    )

    def finalizar(self, forma_pagamento=None):
        """
        Finaliza o pedido e cria a venda de forma segura.
        """
        if self.status == 'finalizado':
            return self.venda if hasattr(self, 'venda') else None

        with transaction.atomic():
            # atualiza status
            self.status = 'finalizado'
            self.save(update_fields=['status'])

            # cria venda se não existir
            venda, created = Venda.objects.get_or_create(
                pedido=self,
                defaults={
                    'valor_pago': self.total_liquido,
                    'forma_pagamento': forma_pagamento,
                    'confirmado': True
                }
            )

            return venda

    FORMA_PAGAMENTO_CHOICES = (
        ('pix', 'PIX'),
        ('credito', 'Cartão de Crédito'),
        ('debito', 'Cartão de Débito'),
    )

    cliente = models.ForeignKey(
        ClientePerfil,
        on_delete=models.PROTECT,
        related_name='pedidos',
        null=True, blank=True
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='criado'
    )

    # 🚚 logística (preenchido só quando sair para entrega)
    distancia_km = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    tempo_estimado_min = models.PositiveIntegerField(
        null=True, blank=True
    )

    # 🔒 snapshot financeiro
    total_bruto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valor_desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    total_liquido = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    forma_pagamento = models.CharField(
        max_length=20,
        choices=FORMA_PAGAMENTO_CHOICES,
        null=True,
        blank=True
    )

    cupom_codigo = models.CharField(max_length=20, blank=True, null=True)
    cupom_percentual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    observacoes = models.TextField(blank=True)

    def __str__(self):
        if self.cliente and self.cliente.user:
            return f"Pedido #{self.id} - {self.cliente.user.username}"
        return f"Pedido #{self.id}"


class ItemPedido(Prime):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name='itens'
    )

    # referência apenas histórica
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.PositiveIntegerField(null=True)
    item_original = GenericForeignKey('content_type', 'object_id')

    nome_item = models.CharField(max_length=255)
    tipo_item = models.CharField(
        max_length=30,
        choices=(
            ('brinquedo', 'Brinquedo'),
            ('combo', 'Combo'),
            ('promocao', 'Promoção'),
        )
    )

    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.nome_item} (x{self.quantidade})"


class EnderecoEntrega(Prime):
    pedido = models.OneToOneField(
        Pedido,
        on_delete=models.CASCADE,
        related_name='endereco'
    )

    telefone = models.CharField(
        max_length=20,
        help_text="Telefone para contato na entrega",
        null=True,
        blank=True
    )

    cep = models.CharField(max_length=9)
    rua = models.CharField(max_length=255)
    numero = models.CharField(max_length=20)
    complemento = models.CharField(max_length=255, blank=True, null=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)

    latitude = models.DecimalField(
        max_digits=50, decimal_places=30, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=50, decimal_places=30, null=True, blank=True
    )

    def geocodificar(self):
        endereco = f"{self.rua}, {self.numero}, {self.bairro}, {self.cidade}, {self.estado}, Brasil"

        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": endereco,
            "format": "json",
            "limit": 1
        }

        headers = {
            "User-Agent": "SeuSistemaEntrega/1.0"
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()

            if not data:
                return None, None

            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])

            self.latitude = lat
            self.longitude = lon
            self.save(update_fields=['latitude', 'longitude'])

            return lat, lon

        except Exception:
            return None, None

    def __str__(self):
        return f"Entrega Pedido #{self.pedido.id} - {self.cidade}/{self.estado}"


class Venda(Prime):
    pedido = models.OneToOneField(
        Pedido,
        on_delete=models.PROTECT,
        related_name='venda',
        null=True
    )

    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    forma_pagamento = models.CharField(max_length=30,
                                       choices=(
                                           ('pix', 'PIX'),
                                           ('cartao', 'Cartão'),
                                           ('dinheiro', 'Dinheiro'),
                                           ('whatsapp', 'WhatsApp'),
                                       ),
                                       null=True

                                       )

    confirmado = models.BooleanField(default=False)
    cpf = models.CharField(max_length=16, null=True)

    def __str__(self):
        return f"Venda do Pedido #{self.pedido.id}"


class Manutencao(models.Model):
    STATUS_CHOICES = [
        ('P', 'Pendente'),
        ('A', 'Em andamento'),
        ('C', 'Concluída'),
        ('X', 'cancelada'),
    ]

    brinquedo = models.ForeignKey(
        Brinquedos,
        on_delete=models.CASCADE,
        related_name='brinquedo_manutencoes'
    )
    descricao = models.TextField(max_length=999)

    usuario = models.ForeignKey(
        ClientePerfil,
        on_delete=models.CASCADE,
        related_name='manutencoes'
    )

    telefone_contato = models.CharField(
        max_length=20,
        help_text="Telefone para contato",
        null=True
    )

    cep = models.CharField(
        max_length=9,
        help_text="Formato: 00000-000",
        null=True
    )
    endereco = models.CharField(max_length=255, null=True)
    numero = models.CharField(max_length=20, null=True)
    complemento = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    bairro = models.CharField(max_length=100, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)

    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES,
        default='P'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"{self.brinquedo} - {self.get_status_display()}"


class ManutencaoImagem(models.Model):
    manutencao = models.ForeignKey(
        Manutencao,
        on_delete=models.CASCADE,
        related_name='imagens'
    )
    imagem = models.ImageField(upload_to='manutencoes/')


class ListaDesejos(Prime):
    brinquedos = models.ManyToManyField(Brinquedos, related_name='lista_desejos')

    def __str__(self):
        return self.brinquedos.nome_brinquedo

    class Meta:
        verbose_name = "Lista de Desejo"
        verbose_name_plural = "Lista de Desejos"


class BrinquedoClick(Prime):
    brinquedo_clicado = models.ForeignKey(Brinquedos, on_delete=models.SET_NULL, related_name='clicks_brinquedo',
                                          null=True)
    quantidade_click = models.IntegerField(default=1)

    def __str__(self):
        return self.brinquedo_clicado.nome_brinquedo

    class Meta:
        verbose_name = "Brinquedo Clicado"
        verbose_name_plural = "Brinquedos Clicados"


class ComboClick(Prime):
    combo_clicado = models.ForeignKey(
        Combos,
        on_delete=models.SET_NULL,
        related_name='clicks_combo',
        null=True,
        blank=True
    )

    # Snapshot dos dados (permanece mesmo se apagar)
    descricao_combo = models.CharField(max_length=90, null=True)
    valor_combo = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    quantidade_click = models.IntegerField(default=1)

    def __str__(self):
        return self.descricao_combo

    class Meta:
        verbose_name = "Combo Clicado"
        verbose_name_plural = "Combos Clicados"


class PromocaoClick(Prime):
    promocao = models.ForeignKey(
        Promocoes,
        on_delete=models.SET_NULL,
        related_name='clicks_promocao',
        null=True,
        blank=True
    )

    # SNAPSHOT (permanece após exclusão)
    descricao_promocao = models.CharField(max_length=120, null=True)
    preco_promocao = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    quantidade_click = models.IntegerField(default=1)

    def __str__(self):
        return self.descricao_promocao

    class Meta:
        verbose_name = "Promoção Clicada"
        verbose_name_plural = "Promoções Clicadas"


class CategoriaClick(Prime):
    categoria = models.ForeignKey(
        CategoriasBrinquedos,
        on_delete=models.SET_NULL,
        related_name='clicks_categoria',
        null=True,
        blank=True
    )

    # SNAPSHOT
    nome_categoria = models.CharField(max_length=150, null=True)

    quantidade_click = models.IntegerField(default=1)

    def __str__(self):
        return self.nome_categoria

    class Meta:
        verbose_name = "Categoria Clicada"
        verbose_name_plural = "Categorias Clicadas"
