import secrets
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.utils.text import slugify
from django.utils import timezone

from core.models import (
    Brinquedos,
    Estabelecimentos,
    ItemPedido,
    PecasReposicao,
    Pedido,
    Venda,
)
from core.utils import buscar_coordenadas_por_cidade, geocodificar_endereco


class Prime(models.Model):
    criacao = models.DateTimeField(auto_now_add=True, null=True)
    atualizado = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class Gerente(Prime):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gerente'
    )

    nome = models.CharField(max_length=120)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"Gerente: {self.nome}"

    class Meta:
        verbose_name = "Gerente"
        verbose_name_plural = "Gerentes"


class Cliente(Prime):
    """Quem compra, aluga ou recebe manutenção da Lazer & Sport.

    UM CADASTRO SÓ, PARA TUDO. Antes eram dois. Este, do painel, guardava
    contato, documento e histórico de proposta; e havia um segundo, do
    site, que existia só para pôr um alfinete no mapa da vitrine. O mesmo
    buffet precisava ser digitado nos dois lugares, e nada obrigava os
    dois cadastros a concordarem: o mapa mostrava o endereço antigo
    enquanto a proposta saía com o novo, e ninguém sabia qual dos dois
    estava certo.

    Agora existe esta tabela e mais nenhuma. O cliente é criado aqui, e o
    mapa público é uma LEITURA deste cadastro -- ``publicar_no_mapa`` diz
    se o alfinete aparece, e o endereço do estabelecimento diz onde.

    O que muda de um cliente para outro é o papel: ``tipo`` separa a casa
    do salão de festas, e ``parceiro`` liga um cliente ao buffet que o
    atende -- é assim que se responde "quais clientes vieram pelo Buffet
    Alegria" sem inventar um cadastro paralelo.
    """

    class Tipo(models.TextChoices):
        """Onde o brinquedo vai parar.

        A distinção não é burocrática: residência quer entrega na porta e
        montagem no quintal; comércio e buffet querem nota, horário de
        carga e alguém no local para receber. Escola e condomínio pedem
        autorização de portaria. Quem monta a rota lê esta coluna antes
        de tudo.

        `pessoa` e `empresa` eram os nomes antigos e viraram
        `residencial` e `comercial` na migração 0020 -- mesmo cadastro,
        nome que diz o que interessa para quem carrega o caminhão.
        """

        RESIDENCIAL = "residencial", "Residencial"
        COMERCIAL = "comercial", "Comercial"
        BUFFET = "buffet", "Buffet parceiro"
        CONDOMINIO = "condominio", "Condomínio"
        ESCOLA = "escola", "Escola"
        ORGAO = "orgao", "Órgão público"

    class CanalTelefone(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp confirmado"
        TELEFONE = "telefone", "Telefone, sem WhatsApp"
        NAO_CONFIRMADO = "nao_confirmado", "Ainda não confirmado"

    nome_cliente = models.CharField("Nome", max_length=90)
    tipo = models.CharField(
        "Tipo de cadastro",
        max_length=12,
        choices=Tipo.choices,
        default=Tipo.RESIDENCIAL,
        db_index=True,
    )
    documento = models.CharField(
        "CPF ou CNPJ",
        max_length=20,
        blank=True,
        help_text="Usado na nota e no contrato. Pode ficar em branco.",
    )
    documento_chave = models.CharField(
        max_length=14,
        blank=True,
        db_index=True,
        editable=False,
        help_text="CPF/CNPJ normalizado, usado apenas para evitar duplicidades.",
    )
    documento_valido = models.BooleanField(
        default=False,
        db_index=True,
        editable=False,
        help_text="Confere formato e dígitos verificadores; não consulta a Receita.",
    )
    # Era max_length=14 -- não cabia "(11) 99999-9999", que tem 15. O
    # cadastro pelo painel quebrava justamente no celular com máscara.
    telefone = models.CharField("Telefone / WhatsApp", max_length=24, blank=True)
    # Só os dígitos do telefone, preenchido no save.
    #
    # POR QUE UMA CÓPIA. Na lista, quem procura digita "11977776655" ou
    # "977776655", e o cadastro está gravado como "(11) 97777-6655".
    # Comparar texto com máscara nunca casa, e limpar a máscara dentro do
    # SQL muda de banco para banco. A cópia limpa resolve com um índice.
    telefone_digitos = models.CharField(
        max_length=20,
        blank=True,
        db_index=True,
        editable=False,
    )
    canal_telefone = models.CharField(
        "Uso do número",
        max_length=16,
        choices=CanalTelefone.choices,
        default=CanalTelefone.NAO_CONFIRMADO,
        help_text="Evita tratar um telefone comum como WhatsApp sem confirmação.",
    )
    email = models.CharField(max_length=150, null=True, blank=True)

    ativo = models.BooleanField(
        "Cadastro ativo",
        default=True,
        help_text="Desmarque para arquivar sem apagar o histórico de propostas.",
    )

    parceiro = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="clientes_atendidos",
        null=True,
        blank=True,
        limit_choices_to={"tipo": Tipo.BUFFET},
        verbose_name="Buffet responsável",
        help_text="Buffet que atende este cliente, quando a festa vem por ele.",
    )
    estabelecimento = models.ForeignKey(
        Estabelecimentos,
        on_delete=models.SET_NULL,
        related_name="clientes_internos",
        null=True,
        blank=True,
        verbose_name="Parceiro publicado no site",
        help_text="Liga este cadastro ao parceiro que aparece no site.",
    )
    nome_estabelecimento = models.CharField("Nome do estabelecimento do cliente", max_length=150, blank=True)
    cnpj_estabelecimento = models.CharField("CNPJ do estabelecimento", max_length=14, blank=True, db_index=True)

    observacoes = models.TextField("Observações", blank=True)

    # ------------------------------------------------------------------
    # O QUE O SITE MOSTRA
    #
    # Três campos, e só. Não é um "cadastro de vitrine" paralelo: é a
    # parte deste cadastro que fica visível para quem não é da casa.
    # ------------------------------------------------------------------
    publicar_no_mapa = models.BooleanField(
        "Aparece no mapa do site",
        default=False,
        db_index=True,
        help_text=(
            "Põe o alfinete deste cliente no mapa da página inicial. "
            "Precisa do endereço do estabelecimento com localização."
        ),
    )
    logo = models.ImageField(
        "Logo do cliente",
        upload_to="logo_clientes/",
        null=True,
        blank=True,
        help_text="Aparece no mapa e na faixa de clientes do rodapé do site.",
    )
    site_cliente = models.URLField(
        "Instagram ou site",
        blank=True,
        null=True,
        help_text='Vira o link "Visitar Instagram" no balão do mapa.',
    )

    @property
    def eh_buffet(self) -> bool:
        return self.tipo == self.Tipo.BUFFET

    @property
    def contato_curto(self) -> str:
        """Primeira forma de falar com o cliente, para caber na lista."""
        return self.telefone or (self.email or "") or "sem contato"

    @property
    def endereco_principal(self):
        """O endereço do estabelecimento; None quando ainda não há.

        É o mesmo endereço que vai ao mapa, à entrega e à montagem --
        um só, de propósito: dois endereços "principais" é como o
        cadastro antigo passava a mostrar coisas diferentes em telas
        diferentes.

        `all()[0]` EM VEZ DE `first()`, e a diferença é de desempenho.
        `first()` monta uma consulta nova (ORDER BY + LIMIT 1) e por isso
        ignora o prefetch que a tela já pagou: na lista de orçamentos
        eram 26 idas ao banco numa página de 25 linhas, uma por linha.
        `all()` devolve o cache do prefetch quando ele existe, e a lista
        de endereços de um cliente tem uma ou duas linhas -- indexar isso
        em memória é de graça.

        Sem prefetch o comportamento é o mesmo de antes: uma consulta.
        """
        enderecos = self.enderecos.all()
        return enderecos[0] if enderecos else None

    @property
    def publicacao_mapa(self):
        if self.publicar_no_mapa:
            return True
        if hasattr(self, "_proposta_mapa"):
            return self._proposta_mapa
        return self.orcamentos.filter(
            status__in=("aguardando_resposta", "em_negociacao", "aprovado")
        ).exists() if self.pk else False

    @property
    def no_mapa(self) -> bool:
        """Está de fato desenhado no mapa, e não só marcado para estar."""
        endereco = self.endereco_principal
        return bool(
            self.publicacao_mapa
            and self.ativo
            and endereco
            and endereco.latitude is not None
            and endereco.longitude is not None
        )

    def save(self, *args, **kwargs):
        from .validacoes import chave_documento, documento_valido, somente_digitos

        self.telefone_digitos = somente_digitos(self.telefone)
        self.documento_chave = chave_documento(self.documento)
        self.documento_valido = documento_valido(self.documento)

        campos = kwargs.get("update_fields")
        if campos is not None:
            campos = set(campos)
            if "telefone" in campos:
                campos.add("telefone_digitos")
            if "documento" in campos:
                campos.update(("documento_chave", "documento_valido"))
            kwargs["update_fields"] = list(campos)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome_cliente

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ("nome_cliente",)
        constraints = [models.UniqueConstraint(fields=["cnpj_estabelecimento"],
            condition=~models.Q(cnpj_estabelecimento=""), name="cliente_cnpj_negocio_unico")]



class EnderecoCliente(Prime):
    """Onde o brinquedo é entregue, montado -- e onde cai o alfinete.

    Um por cliente. O endereço do estabelecimento é este; não existe um
    "endereço do mapa" separado, que era justamente o que fazia a vitrine
    e a proposta discordarem.
    """

    class Precisao(models.TextChoices):
        """Até onde a busca automática conseguiu chegar.

        Guardar isto é o que permite distinguir, depois, um alfinete no
        endereço de um alfinete no meio do município -- e é a diferença
        entre "o motorista chega" e "o motorista liga perguntando".
        """

        EXATO = "exato", "Endereço exato"
        RUA = "rua", "Meio da rua"
        BAIRRO = "bairro", "Centro do bairro"
        CIDADE = "cidade", "Centro da cidade"
        MANUAL = "manual", "Informada à mão"

    cep = models.CharField(max_length=18, blank=True)
    endereco = models.CharField(max_length=120)
    numero = models.CharField(max_length=10, blank=True)
    complemento = models.CharField(max_length=60, blank=True)
    bairro = models.CharField(max_length=50, blank=True)
    cidade = models.CharField(max_length=60)
    estado = models.CharField(max_length=20, blank=True)
    pais = models.CharField(
        max_length=60,
        default="Brasil",
        help_text="Cliente fora do Brasil não tem CEP: preencha cidade, estado e país.",
    )
    cliente = models.ForeignKey(
        Cliente, related_name="enderecos", on_delete=models.CASCADE, null=True
    )

    latitude = models.DecimalField(
        max_digits=50, decimal_places=30, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=50, decimal_places=30, null=True, blank=True
    )
    precisao = models.CharField(
        max_length=10, choices=Precisao.choices, blank=True, default=""
    )

    @property
    def linha_curta(self) -> str:
        """Uma linha, para caber na lista e no balão do mapa."""
        pedacos = [p for p in (self.cidade, self.estado) if p]
        return "/".join(pedacos) if pedacos else (self.pais or "")

    @property
    def tem_local(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    def localizar(self):
        """Procura a coordenada deste endereço, sem apagar a que já existe.

        Nunca é chamada dentro de um `save`. Geocodificação é uma consulta
        a serviço de fora: prender a gravação do cadastro a ela é como o
        painel travava quando a fonte estava fora do ar -- e o cadastro
        que a pessoa acabou de digitar se perdia junto.
        """
        if self.tem_local:
            return False

        latitude = longitude = precisao = None

        if self.cep:
            latitude, longitude, precisao = geocodificar_endereco(
                self.cep, self.numero or ""
            )

        if (not latitude or not longitude) and self.cidade:
            latitude, longitude = buscar_coordenadas_por_cidade(
                self.cidade, self.estado or "", self.pais or "Brasil"
            )
            # Sem CEP só dá para chegar na cidade.
            precisao = self.Precisao.CIDADE if latitude and longitude else None

        if not (latitude and longitude):
            return False

        self.latitude = latitude
        self.longitude = longitude
        self.precisao = precisao or ""
        return True

    def __str__(self):
        return self.endereco

    class Meta:
        constraints = [models.UniqueConstraint(
            models.F("cliente"),
            *[models.functions.Lower(models.functions.Trim(models.F(campo)))
              for campo in ("endereco", "numero", "complemento", "cidade", "estado", "pais")],
            name="endereco_cliente_local_unico",
        )]
        verbose_name = "Endereço do Cliente"
        verbose_name_plural = "Endereços dos Clientes"


class Fornecedor(Prime):
    """Quem vende o material. O preço pago fica no estoque, não aqui:
    o mesmo fornecedor muda de preço a cada compra."""

    nome = models.CharField(max_length=120, unique=True)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=150, blank=True)
    cnpj = models.CharField("CNPJ / CPF", max_length=20, blank=True)
    site = models.CharField(max_length=200, blank=True)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"
        ordering = ("nome",)


class SequenciaMaterial(models.Model):
    """Reserva permanente do prefixo; excluir um item não reutiliza seu código."""
    prefixo = models.CharField(max_length=16, primary_key=True)
    ultimo = models.PositiveBigIntegerField(default=0)


class TipoMaterial(Prime):
    descricao = models.CharField(max_length=120)
    prefixo = models.CharField(max_length=16, unique=True, null=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        if self.prefixo:
            return super().save(*args, **kwargs)
        banco = kwargs.get("using") or self._state.db or "default"
        base = slugify(self.descricao).replace("-", "")[:3] or "tip"
        # 'mat' é reservado aos materiais sem tipo.
        indice = 2 if base == "mat" else 1
        with transaction.atomic(using=banco):
            while True:
                prefixo = base if indice == 1 else f"{base}{indice}"
                try:
                    with transaction.atomic(using=banco):
                        SequenciaMaterial.objects.using(banco).create(prefixo=prefixo)
                    break
                except IntegrityError:
                    indice += 1
            self.prefixo = prefixo
            if kwargs.get("update_fields"):
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"prefixo"}
            return super().save(*args, **kwargs)

    def __str__(self):
        return self.descricao

    class Meta:
        verbose_name = "Tipo de Material"
        verbose_name_plural = "Tipos de Materiais"


class Material(Prime):
    class Unidade(models.TextChoices):
        UNIDADE = "un", "Unidade"
        PECA = "pc", "Peça"
        METRO = "m", "Metro"
        METRO_QUADRADO = "m2", "Metro quadrado"
        QUILO = "kg", "Quilo"
        LITRO = "l", "Litro"
        CAIXA = "cx", "Caixa"
        ROLO = "rl", "Rolo"
        PAR = "par", "Par"

    nome_material = models.CharField(max_length=90)
    descricao = models.CharField(max_length=150, null=True, blank=True)
    codigo_interno = models.CharField(
        "Código interno",
        max_length=30,
        blank=True,
        help_text="Gerado automaticamente por tipo. Códigos anteriores são preservados.",
    )
    foto = models.ImageField(upload_to="materiais/fotos/", blank=True)
    foto_miniatura = models.ImageField(upload_to="materiais/miniaturas/", blank=True, editable=False)
    unidade = models.CharField(
        max_length=5,
        choices=Unidade.choices,
        default=Unidade.UNIDADE,
    )
    tipo_material = models.ForeignKey(TipoMaterial, on_delete=models.SET_NULL, related_name='material', null=True, blank=True)
    brinquedos_associados = models.ManyToManyField(Brinquedos, related_name='materiais', blank=True)
    ativo = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if self.codigo_interno:
            return super().save(*args, **kwargs)
        banco = kwargs.get("using") or self._state.db or "default"
        prefixo = self.tipo_material.prefixo if self.tipo_material_id else "mat"
        with transaction.atomic(using=banco):
            SequenciaMaterial.objects.using(banco).get_or_create(prefixo=prefixo)
            sequencia = SequenciaMaterial.objects.using(banco).select_for_update().get(pk=prefixo)
            while True:
                sequencia.ultimo += 1
                codigo = f"{prefixo}-{sequencia.ultimo:04d}"
                if not Material.objects.using(banco).filter(codigo_interno__iexact=codigo).exists():
                    break
            sequencia.save(using=banco, update_fields=["ultimo"])
            self.codigo_interno = codigo
            if kwargs.get("update_fields"):
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"codigo_interno"}
            return super().save(*args, **kwargs)

    @property
    def quantidade_total(self):
        """Soma o que existe em todos os locais de guarda."""
        return sum(local.quantidade for local in self.estoque.all())

    @property
    def valor_total(self):
        """Quanto foi pago pelo que ainda está guardado."""
        return sum(
            (local.valor_total for local in self.estoque.all()),
            Decimal("0.00"),
        )

    def __str__(self):
        return self.nome_material

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "materiais"
        ordering = ("nome_material",)


class HistoricoCodigoMaterial(Prime):
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="historico_codigos")
    anterior = models.CharField(max_length=30, blank=True)
    novo = models.CharField(max_length=30)


class Colaborador(Prime):
    """Pessoa da fábrica citada na produção, sem conta de acesso.

    O usuário registra ações no sistema para auditoria. O colaborador diz
    quem está montando fisicamente o brinquedo. Misturar os dois obrigava
    a criar login para alguém que só precisava aparecer na ordem.
    """

    nome = models.CharField(max_length=90)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Colaborador"
        verbose_name_plural = "Colaboradores"
        ordering = ("nome",)


class Setores(Prime):
    nome_setor = models.CharField(max_length=120)

    def __str__(self):
        return self.nome_setor

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "Setores"


class EstoqueMaterialQuerySet(models.QuerySet):
    """A regra de "crítico" escrita como consulta, uma vez só.

    `situacao` é propriedade Python: perfeita para uma linha na tela,
    péssima para contar a tabela. Antes cada lugar que precisava da lista
    de reposição carregava tudo e filtrava na memória -- a visão geral, o
    painel de estoque e a central de avisos, três vezes a mesma varredura.

    Aqui a conta é a MESMA de `situacao == CRITICO` (quantidade no mínimo
    ou abaixo dele), só que resolvida pelo banco. Há teste comparando os
    dois caminhos justamente para não deixarem de concordar.
    """

    def criticos(self):
        return self.filter(quantidade__lte=models.F("estoque_minimo"))


class EstoqueMaterial(Prime):
    """Um material guardado num local. É aqui que fica o valor pago."""

    objects = EstoqueMaterialQuerySet.as_manager()

    ESTAVEL = "estavel"
    ATENCAO = "atencao"
    CRITICO = "critico"

    descricao_local = models.CharField("Local de guarda", max_length=90)
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='estoque')
    quantidade = models.IntegerField(default=1)
    # max_digits=6 travava o cadastro em R$ 9.999,99, o que não cobre
    # lona, motor, inflável nem compra fechada de fornecedor.
    preco_fornecedor = models.DecimalField(
        "Custo médio por unidade",
        decimal_places=2,
        max_digits=12,
    )
    saldo_valor = models.DecimalField(max_digits=22, decimal_places=2, null=True, blank=True, editable=False)
    custo_estimado = models.BooleanField(default=False, editable=False)

    def save(self, *args, **kwargs):
        if self.saldo_valor is None:
            self.saldo_valor = (Decimal(str(self.preco_fornecedor or 0)) * max(self.quantidade, 0)).quantize(Decimal("0.01"))
        return super().save(*args, **kwargs)
    fornecedor = models.ForeignKey(
        Fornecedor,
        on_delete=models.SET_NULL,
        related_name="estoques",
        null=True,
        blank=True,
    )
    estoque_minimo = models.PositiveIntegerField(
        "Quantidade mínima",
        default=0,
        help_text="Abaixo disso o item entra na lista de reposição.",
    )
    nota_fiscal = models.CharField(max_length=60, blank=True)
    comprado_em = models.DateField("Data da compra", null=True, blank=True)
    observacoes = models.TextField(blank=True)

    @property
    def valor_total(self):
        if self.saldo_valor is not None:
            return self.saldo_valor
        preco = self.preco_fornecedor or Decimal("0.00")
        return (preco * max(self.quantidade, 0)).quantize(Decimal("0.01"))

    @property
    def situacao(self):
        minimo = self.estoque_minimo or 0
        if self.quantidade <= minimo:
            return self.CRITICO
        if minimo and self.quantidade <= minimo * 2:
            return self.ATENCAO
        if not minimo and self.quantidade <= 5:
            return self.ATENCAO
        return self.ESTAVEL

    @property
    def situacao_label(self):
        return {
            self.CRITICO: "Repor agora",
            self.ATENCAO: "Atenção",
            self.ESTAVEL: "Estável",
        }[self.situacao]

    def __str__(self):
        return f"{self.material} - {self.descricao_local}"

    class Meta:
        verbose_name = "Estoque de Material"
        verbose_name_plural = "Estoque de Materiais"
        unique_together = ('material', 'descricao_local')
        ordering = ("material__nome_material", "descricao_local")


class MovimentoEstoque(Prime):
    """Histórico de entrada, saída e acerto de contagem.

    A quantidade do estoque só muda por aqui: sem isso, um número
    corrigido na mão não deixa rastro de quem mexeu nem de quanto
    foi pago.
    """

    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada (compra)"
        SAIDA = "saida", "Saída (uso / montagem)"
        AJUSTE = "ajuste", "Ajuste de contagem"

    estoque = models.ForeignKey(
        EstoqueMaterial,
        on_delete=models.PROTECT,
        related_name="movimentos",
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices, db_index=True)
    quantidade = models.PositiveIntegerField()
    quantidade_resultante = models.IntegerField(default=0)
    valor_unitario = models.DecimalField(
        "Valor pago por unidade",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    documento = models.CharField(
        "Nota / pedido",
        max_length=60,
        blank=True,
    )
    motivo = models.CharField(max_length=150, blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="movimentos_estoque",
        null=True,
        blank=True,
    )
    ocorrido_em = models.DateTimeField(default=timezone.now, db_index=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.SET_NULL, null=True, blank=True, related_name="compras_registradas")
    fornecedor_nome = models.CharField(max_length=120, blank=True)
    data_compra = models.DateField(null=True, blank=True)
    variacao_valor = models.DecimalField(max_digits=22, decimal_places=2, null=True, blank=True, editable=False)
    saldo_valor_resultante = models.DecimalField(max_digits=22, decimal_places=2, null=True, blank=True, editable=False)
    custo_estimado = models.BooleanField(default=False, editable=False)

    @property
    def valor_total(self):
        if self.tipo != self.Tipo.ENTRADA:
            if self.variacao_valor is None:
                return None  # O histórico antigo não registrava o custo efetivo da baixa.
            return -self.variacao_valor if self.tipo == self.Tipo.SAIDA else self.variacao_valor
        if self.valor_unitario is None:
            return None
        return (self.valor_unitario * self.quantidade).quantize(Decimal("0.01"))

    @classmethod
    @transaction.atomic
    def registrar(cls, estoque, tipo, quantidade, **extras):
        """Aplica o movimento e devolve o registro já salvo.

        select_for_update evita que duas baixas simultâneas leiam a
        mesma quantidade e gravem o mesmo resultado.
        """
        if tipo not in cls.Tipo.values:
            raise ValueError("Tipo de movimento inválido.")
        if Decimal(str(quantidade)) != int(quantidade):
            raise ValueError("Informe uma quantidade inteira.")
        quantidade = int(quantidade)
        if quantidade < 0 or (quantidade == 0 and tipo != cls.Tipo.AJUSTE):
            raise ValueError("Informe uma quantidade maior que zero.")

        travado = (
            EstoqueMaterial.objects
            .select_for_update()
            .get(pk=estoque.pk)
        )

        if tipo == cls.Tipo.ENTRADA:
            resultante = travado.quantidade + quantidade
        elif tipo == cls.Tipo.SAIDA:
            if quantidade > travado.quantidade:
                raise ValueError(
                    f"Saída de {quantidade} maior que o saldo atual "
                    f"({travado.quantidade})."
                )
            resultante = travado.quantidade - quantidade
        else:
            resultante = quantidade

        if resultante < 0 or resultante > 2147483647:
            raise ValueError("O saldo resultante está fora do limite permitido.")

        saldo_anterior = travado.valor_total
        medio = saldo_anterior / travado.quantidade if travado.quantidade else Decimal(str(travado.preco_fornecedor))
        estimado = travado.custo_estimado
        if tipo == cls.Tipo.ENTRADA:
            valor = extras.get("valor_unitario")
            if valor is None:
                raise ValueError("Informe o preço unitário desta compra, inclusive se for zero.")
            valor = Decimal(str(valor))
            if not valor.is_finite() or valor < 0 or valor > Decimal("9999999999.99"):
                raise ValueError("Preço unitário inválido.")
            valor = valor.quantize(Decimal("0.01"))
            extras["valor_unitario"] = valor
            variacao = (valor * quantidade).quantize(Decimal("0.01"))
            fornecedor = extras.get("fornecedor")
            extras["fornecedor_nome"] = fornecedor.nome if fornecedor else ""
        else:
            if tipo == cls.Tipo.AJUSTE and not str(extras.get("motivo", "")).strip():
                raise ValueError("Informe o motivo do ajuste de contagem.")
            extras["valor_unitario"] = medio.quantize(Decimal("0.01"))
            variacao = ((resultante - travado.quantidade) * medio).quantize(Decimal("0.01"))
            extras.pop("fornecedor", None)
            extras.pop("data_compra", None)
        # A última baixa zera também os centavos residuais.
        if resultante == 0:
            variacao = -saldo_anterior
        if tipo == cls.Tipo.AJUSTE and resultante > travado.quantidade and not travado.quantidade:
            estimado = True
        travado.quantidade = resultante
        travado.saldo_valor = saldo_anterior + variacao
        travado.preco_fornecedor = (travado.saldo_valor / resultante).quantize(Decimal("0.01")) if resultante else Decimal("0.00")
        travado.custo_estimado = estimado if resultante else False
        travado.save(update_fields=["quantidade", "saldo_valor", "preco_fornecedor", "custo_estimado", "atualizado"])
        extras.update(variacao_valor=variacao, saldo_valor_resultante=travado.saldo_valor, custo_estimado=estimado)

        return cls.objects.create(
            estoque=travado,
            tipo=tipo,
            quantidade=quantidade,
            quantidade_resultante=resultante,
            **extras,
        )

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.estoque}"

    class Meta:
        verbose_name = "Movimento de Estoque"
        verbose_name_plural = "Movimentos de Estoque"
        ordering = ("-ocorrido_em", "-id")

class CentralPedidos(Prime):

    class StatusPedido(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        EM_ANDAMENTO = "andamento", "Em andamento"
        CONCLUIDO = "concluido", "Concluído"
        CANCELADO = "cancelado", "Cancelado"

    status = models.CharField(
        max_length=20,
        choices=StatusPedido.choices,
        default=StatusPedido.PENDENTE,
        db_index=True
    )
    descricao_pedido = models.CharField(max_length=90)

    def __str__(self):
        return self.descricao_pedido

    class Meta:
        verbose_name = "Central de Pedido"
        verbose_name_plural = "Central de Vendas"


class CentralVendas(Venda):
    origem = models.CharField(
        choices=(
            ('site', 'Site'),
            ('interno', 'Atendimento interno'),
            ('ambulante', 'Vendedor ambulante'),
        ),
        max_length=20, null=True
    )

    def __str__(self):
        return self.origem

    class Meta:
        verbose_name = "Central de Vendas"


class ComprasMensais(Prime):
    descricao_compra = models.CharField(max_length=120)
    valor = models.DecimalField(decimal_places=2, max_digits=12)

    def __str__(self):
        return self.descricao_compra

    class Meta:
        verbose_name = "Compra Mensal"
        verbose_name_plural = "Compras Mensais"


class ItensCompra(Prime):
    compra = models.ForeignKey(ComprasMensais, related_name='itens', on_delete=models.CASCADE, null=True)
    material = models.ForeignKey(Material, on_delete=models.CASCADE, null=True)
    quantidade = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.material.nome_material if self.material else "Item"


class CategoriaDespesa(Prime):
    nome_categoria = models.CharField(max_length=120)

    def __str__(self):
        return self.nome_categoria

    class Meta:
        verbose_name = "Categoria de Despesa"
        verbose_name_plural = "Categorias de Despesas"


class DespesasMensais(Prime):
    descricao_despesa = models.CharField(max_length=90)
    valor_despesa = models.DecimalField(decimal_places=2, max_digits=12)
    categoria_despesa = models.ForeignKey(CategoriaDespesa, on_delete=models.SET_NULL, related_name='despesas',
                                          null=True)

    def __str__(self):
        return self.descricao_despesa

    class Meta:
        verbose_name = "Despesa Mensal"
        verbose_name_plural = "Despesas Mensais"


class FinanceiroMensal(Prime):
    descricao = models.CharField(max_length=90)
    despesas_mensais = models.ManyToManyField(DespesasMensais, related_name='financeiros')
    mes = models.DateField(null=True)
    valor_liquido = models.DecimalField(max_digits=12, decimal_places=2)
    valor_bruto = models.DecimalField(max_digits=12, decimal_places=2)
    lucro = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.descricao

    class Meta:
        verbose_name = "Financeiro Mensal"
        verbose_name_plural = "Financeiros Mensais"


# ======================================================================
# PRODUÇÃO — o que a fábrica monta e do que é feito
# ======================================================================
class ProdutoInterno(Prime):
    """Uma máquina ou produto que a fábrica monta.

    Existe separado de `core.Brinquedos` de propósito: o catálogo do site
    é vitrine (foto, preço, descrição de venda) e nem tudo que a fábrica
    produz vai para a loja. Quando o produto também está no site, o campo
    `brinquedo` faz a ponte entre os dois.
    """

    class Categoria(models.TextChoices):
        MAQUINA = "maquina", "Máquina"
        BRINQUEDO = "brinquedo", "Brinquedo"
        PECA = "peca", "Peça / componente"
        OUTRO = "outro", "Outro"

    nome = models.CharField(max_length=120)
    codigo = models.CharField(
        "Código de produção",
        max_length=30,
        blank=True,
        help_text="Código usado na ordem de serviço e na etiqueta.",
    )
    categoria = models.CharField(
        max_length=15,
        choices=Categoria.choices,
        default=Categoria.MAQUINA,
        db_index=True,
    )
    brinquedo = models.ForeignKey(
        Brinquedos,
        on_delete=models.SET_NULL,
        related_name="produtos_internos",
        null=True,
        blank=True,
        help_text="Item correspondente no catálogo do site, quando houver.",
    )
    descricao = models.TextField(blank=True)
    horas_producao = models.DecimalField(
        "Horas de montagem",
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    preco_venda = models.DecimalField(
        "Preço de venda sugerido",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    ativo = models.BooleanField(default=True)

    # ---------------------------------------------------------------- custo
    @property
    def custo_materiais(self):
        """Soma o preço de referência de cada material da ficha técnica."""
        return sum(
            (item.custo_estimado for item in self.ficha.all()),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))

    @property
    def margem_estimada(self):
        """Preço de venda menos o custo de material. Sem ficha, devolve None."""
        if not self.preco_venda:
            return None
        return (self.preco_venda - self.custo_materiais).quantize(Decimal("0.01"))

    # ------------------------------------------------------------ produção
    @property
    def possivel_produzir(self):
        """Quantas unidades o estoque atual sustenta.

        É o menor limite entre os materiais da ficha: o material mais
        escasso é quem define o teto da produção. Produto sem ficha
        técnica devolve None — não dá para afirmar nada sobre ele.
        """
        itens = list(self.ficha.all())
        if not itens:
            return None

        limites = [item.unidades_possiveis for item in itens]
        return min(limites) if limites else 0

    @property
    def gargalo(self):
        """O item da ficha que segura a produção. Serve para a tela de compras."""
        itens = list(self.ficha.all())
        if not itens:
            return None
        return min(itens, key=lambda item: item.unidades_possiveis)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Produto de produção"
        verbose_name_plural = "Produtos de produção"
        ordering = ("nome",)


class ItemFichaTecnica(Prime):
    """Quanto de cada material entra em uma unidade do produto."""

    produto = models.ForeignKey(
        ProdutoInterno,
        on_delete=models.CASCADE,
        related_name="ficha",
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="fichas",
    )
    quantidade = models.DecimalField(
        "Quantidade por unidade",
        max_digits=10,
        decimal_places=3,
        default=Decimal("1.000"),
    )
    observacao = models.CharField(max_length=150, blank=True)

    @property
    def disponivel(self):
        """Saldo do material somando todos os locais de guarda."""
        return sum(local.quantidade for local in self.material.estoque.all())

    @property
    def unidades_possiveis(self):
        """Quantas unidades do produto este material sozinho sustenta."""
        if self.quantidade <= 0:
            return 0
        return int(Decimal(self.disponivel) // self.quantidade)

    @property
    def preco_referencia(self):
        """Custo médio ponderado dos saldos disponíveis, não a última compra."""
        locais = list(self.material.estoque.filter(quantidade__gt=0))
        quantidade = sum(local.quantidade for local in locais)
        return sum((local.valor_total for local in locais), Decimal("0.00")) / quantidade if quantidade else Decimal("0.00")

    @property
    def custo_estimado(self):
        return (self.preco_referencia * self.quantidade).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.material} x {self.quantidade}"

    class Meta:
        verbose_name = "Item da ficha técnica"
        verbose_name_plural = "Itens da ficha técnica"
        unique_together = ("produto", "material")
        ordering = ("material__nome_material",)


class GuiaEtapaProducao(Prime):
    """Uma etapa do manual de fabricação de um produto.

    O guia pertence ao produto interno, não a um pedido do site. A ordem
    numérica define a sequência que o colaborador precisa seguir.
    """

    produto = models.ForeignKey(
        ProdutoInterno,
        on_delete=models.CASCADE,
        related_name="guias_producao",
    )
    ordem = models.PositiveIntegerField(default=1)
    titulo = models.CharField(max_length=120)
    instrucoes = models.TextField(
        help_text="Explique, em detalhes, como executar esta etapa.",
    )
    criterio_conclusao = models.TextField(
        "Como conferir o resultado",
        blank=True,
    )
    tempo_estimado_min = models.PositiveIntegerField(
        "Tempo estimado (minutos)",
        null=True,
        blank=True,
    )
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.produto} · {self.ordem}. {self.titulo}"

    class Meta:
        verbose_name = "Etapa do guia de produção"
        verbose_name_plural = "Etapas dos guias de produção"
        ordering = ("produto__nome", "ordem", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("produto", "ordem"),
                name="guia_etapa_ordem_unica_por_produto",
            ),
        ]


class ImagemGuiaProducao(Prime):
    etapa = models.ForeignKey(
        GuiaEtapaProducao,
        on_delete=models.CASCADE,
        related_name="imagens",
    )
    imagem = models.ImageField(upload_to="producao/guias/")
    legenda = models.CharField(max_length=160, blank=True)
    ordem = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Imagem de {self.etapa}"

    class Meta:
        verbose_name = "Imagem do guia de produção"
        verbose_name_plural = "Imagens dos guias de produção"
        ordering = ("ordem", "id")


class OrdemProducao(Prime):
    """Uma rodada de produção: o que foi montado, quanto e por quem."""

    class Status(models.TextChoices):
        PLANEJADA = "planejada", "Planejada"
        EM_PRODUCAO = "producao", "Em produção"
        PAUSADA = "pausada", "Pausada"
        BLOQUEADA = "bloqueada", "Bloqueada"
        CONCLUIDA = "concluida", "Concluída"
        CANCELADA = "cancelada", "Cancelada"

    produto = models.ForeignKey(
        ProdutoInterno,
        on_delete=models.PROTECT,
        related_name="ordens",
    )
    quantidade = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PLANEJADA,
        db_index=True,
    )
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        related_name="ordens",
        null=True,
        blank=True,
        help_text="Pessoa que está montando o brinquedo; não é uma conta do sistema.",
    )
    setor = models.ForeignKey(
        Setores,
        on_delete=models.SET_NULL,
        related_name="ordens",
        null=True,
        blank=True,
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ordens_producao",
        null=True,
        blank=True,
    )
    prevista_para = models.DateField(null=True, blank=True)
    concluida_em = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True)

    # Só pode dar baixa uma vez: sem esta trava, reabrir e concluir de novo
    # consumiria o estoque duas vezes pela mesma produção.
    baixa_aplicada = models.BooleanField(default=False)

    @property
    def materiais_necessarios(self):
        """Lista (item da ficha, total necessário, saldo) para a tela."""
        linhas = []
        for item in self.produto.ficha.all():
            necessario = (item.quantidade * self.quantidade)
            linhas.append({
                "item": item,
                "material": item.material,
                "necessario": necessario,
                "disponivel": item.disponivel,
                "suficiente": Decimal(item.disponivel) >= necessario,
            })
        return linhas

    @property
    def tem_material(self):
        linhas = self.materiais_necessarios
        return bool(linhas) and all(linha["suficiente"] for linha in linhas)

    @property
    def progresso_percentual(self):
        etapas = list(self.etapas_execucao.all())
        if not etapas:
            return 0
        concluidas = sum(
            etapa.status == ExecucaoEtapaProducao.Status.CONCLUIDA
            for etapa in etapas
        )
        return round((concluidas / len(etapas)) * 100)

    def preparar_etapas(self):
        """Cria o checklist da ordem a partir do guia ativo do produto."""
        guias = list(
            self.produto.guias_producao
            .filter(ativo=True)
            .order_by("ordem", "id")
        )
        if not guias:
            raise ValueError(
                "Este produto ainda não possui um guia de produção. "
                "Cadastre as etapas antes de criar a ordem."
            )

        invalidas = [guia.titulo for guia in guias if not guia.instrucoes.strip()]
        if invalidas:
            raise ValueError(
                "Todas as etapas precisam ter instruções. Confira: "
                + ", ".join(invalidas)
            )

        existentes = set(
            self.etapas_execucao.values_list("guia_etapa_id", flat=True)
        )
        ExecucaoEtapaProducao.objects.bulk_create([
            ExecucaoEtapaProducao(ordem_producao=self, guia_etapa=guia)
            for guia in guias
            if guia.pk not in existentes
        ])
        return self.etapas_execucao.count()

    @transaction.atomic
    def concluir(self, usuario=None):
        """Fecha a ordem e dá baixa no estoque de cada material da ficha.

        A baixa passa por MovimentoEstoque.registrar para herdar a trava de
        concorrência e deixar o mesmo rastro de qualquer outra saída — quem
        olhar o histórico do material vê a ordem que consumiu a peça.
        """
        if self.baixa_aplicada:
            raise ValueError("Esta ordem já deu baixa no estoque.")

        if self.status == self.Status.CANCELADA:
            raise ValueError("Ordem cancelada não pode ser concluída.")

        itens = list(self.produto.ficha.select_related("material"))
        if not itens:
            raise ValueError(
                "O produto não tem ficha técnica: cadastre os materiais "
                "antes de concluir a produção."
            )

        for item in itens:
            necessario = item.quantidade * self.quantidade

            # A quantidade em estoque é inteira; frações da ficha (0,5 m de
            # lona) são arredondadas para cima para não baixar menos do que
            # a produção realmente consumiu.
            consumir = int(necessario.to_integral_value(rounding="ROUND_CEILING"))
            if consumir <= 0:
                continue

            locais = list(
                item.material.estoque
                .filter(quantidade__gt=0)
                .order_by("-quantidade")
            )

            restante = consumir
            for local in locais:
                if restante <= 0:
                    break

                baixa = min(restante, local.quantidade)
                MovimentoEstoque.registrar(
                    local,
                    MovimentoEstoque.Tipo.SAIDA,
                    baixa,
                    motivo=f"Produção OP #{self.pk} — {self.produto.nome}",
                    responsavel=usuario,
                )
                restante -= baixa

            if restante > 0:
                raise ValueError(
                    f"Estoque insuficiente de {item.material.nome_material}: "
                    f"faltam {restante} para concluir a ordem."
                )

        self.status = self.Status.CONCLUIDA
        self.concluida_em = timezone.now()
        self.baixa_aplicada = True
        self.save(update_fields=["status", "concluida_em", "baixa_aplicada", "atualizado"])
        return self

    def __str__(self):
        return f"OP #{self.pk} — {self.produto} x{self.quantidade}"

    class Meta:
        verbose_name = "Ordem de produção"
        verbose_name_plural = "Ordens de produção"
        ordering = ("-criacao", "-id")


class ExecucaoEtapaProducao(Prime):
    """Andamento de uma etapa específica dentro de uma ordem."""

    class Status(models.TextChoices):
        AGUARDANDO = "aguardando", "Aguardando"
        EM_ANDAMENTO = "andamento", "Em andamento"
        PAUSADA = "pausada", "Pausada"
        BLOQUEADA = "bloqueada", "Bloqueada / com dúvida"
        CONCLUIDA = "concluida", "Concluída"

    ordem_producao = models.ForeignKey(
        OrdemProducao,
        on_delete=models.CASCADE,
        related_name="etapas_execucao",
    )
    guia_etapa = models.ForeignKey(
        GuiaEtapaProducao,
        on_delete=models.PROTECT,
        related_name="execucoes",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.AGUARDANDO,
        db_index=True,
    )
    iniciado_em = models.DateTimeField(null=True, blank=True)
    concluido_em = models.DateTimeField(null=True, blank=True)
    observacao = models.TextField(blank=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="etapas_producao_atualizadas",
        null=True,
        blank=True,
    )

    @classmethod
    @transaction.atomic
    def registrar_acao(cls, execucao_id, acao, usuario, observacao=""):
        """Atualiza uma etapa com trava e sem permitir pular a sequência."""
        execucao = (
            cls.objects
            .select_for_update()
            .select_related("guia_etapa", "ordem_producao")
            .get(pk=execucao_id)
        )
        ordem = (
            OrdemProducao.objects
            .select_for_update()
            .get(pk=execucao.ordem_producao_id)
        )

        if ordem.status in (OrdemProducao.Status.CONCLUIDA, OrdemProducao.Status.CANCELADA):
            raise ValueError("Esta ordem já foi encerrada e não aceita alterações.")

        etapas = list(
            cls.objects
            .filter(ordem_producao=ordem)
            .select_related("guia_etapa")
            .order_by("guia_etapa__ordem", "guia_etapa_id")
        )
        etapa_atual = next(
            (item for item in etapas if item.status != cls.Status.CONCLUIDA),
            None,
        )
        if etapa_atual is None or etapa_atual.pk != execucao.pk:
            raise ValueError(
                "Conclua a etapa atual antes de avançar para a próxima."
            )

        transicoes = {
            "iniciar": ({cls.Status.AGUARDANDO}, cls.Status.EM_ANDAMENTO),
            "pausar": ({cls.Status.EM_ANDAMENTO}, cls.Status.PAUSADA),
            "bloquear": (
                {cls.Status.AGUARDANDO, cls.Status.EM_ANDAMENTO, cls.Status.PAUSADA},
                cls.Status.BLOQUEADA,
            ),
            "retomar": (
                {cls.Status.PAUSADA, cls.Status.BLOQUEADA},
                cls.Status.EM_ANDAMENTO,
            ),
            "concluir": ({cls.Status.EM_ANDAMENTO}, cls.Status.CONCLUIDA),
        }
        if acao not in transicoes:
            raise ValueError("Ação inválida para a etapa de produção.")

        permitidos, novo_status = transicoes[acao]
        if execucao.status not in permitidos:
            raise ValueError(
                f"Não é possível {acao} uma etapa que está "
                f"{execucao.get_status_display().lower()}."
            )

        observacao = (observacao or "").strip()
        if acao == "bloquear" and not observacao:
            raise ValueError(
                "Explique a dúvida ou o problema antes de bloquear a etapa."
            )

        anterior = execucao.status
        agora = timezone.now()
        execucao.status = novo_status
        execucao.atualizado_por = usuario
        if observacao:
            execucao.observacao = observacao
        if novo_status == cls.Status.EM_ANDAMENTO and not execucao.iniciado_em:
            execucao.iniciado_em = agora
        if novo_status == cls.Status.CONCLUIDA:
            execucao.concluido_em = agora

        execucao.save(update_fields=[
            "status", "atualizado_por", "observacao", "iniciado_em",
            "concluido_em", "atualizado",
        ])

        if novo_status == cls.Status.PAUSADA:
            ordem.status = OrdemProducao.Status.PAUSADA
        elif novo_status == cls.Status.BLOQUEADA:
            ordem.status = OrdemProducao.Status.BLOQUEADA
        else:
            ordem.status = OrdemProducao.Status.EM_PRODUCAO

        todas_concluidas = all(
            item.pk == execucao.pk or item.status == cls.Status.CONCLUIDA
            for item in etapas
        )
        if novo_status == cls.Status.CONCLUIDA and todas_concluidas:
            ordem.concluir(usuario=usuario)
        else:
            ordem.save(update_fields=["status", "atualizado"])

        HistoricoProducao.objects.create(
            ordem_producao=ordem,
            etapa=execucao,
            usuario=usuario,
            evento=HistoricoProducao.Evento.ETAPA_ATUALIZADA,
            status_anterior=anterior,
            status_novo=novo_status,
            observacao=observacao,
        )
        return execucao

    def __str__(self):
        return f"{self.ordem_producao} · {self.guia_etapa.titulo}"

    class Meta:
        verbose_name = "Execução de etapa de produção"
        verbose_name_plural = "Execuções de etapas de produção"
        ordering = ("guia_etapa__ordem", "guia_etapa_id")
        constraints = [
            models.UniqueConstraint(
                fields=("ordem_producao", "guia_etapa"),
                name="execucao_unica_por_ordem_e_etapa",
            ),
        ]


class HistoricoProducao(Prime):
    class Evento(models.TextChoices):
        ORDEM_CRIADA = "ordem_criada", "Ordem criada"
        ORDEM_EDITADA = "ordem_editada", "Ordem editada"
        ETAPA_ATUALIZADA = "etapa", "Etapa atualizada"
        ORDEM_CANCELADA = "cancelada", "Ordem cancelada"

    ordem_producao = models.ForeignKey(
        OrdemProducao,
        on_delete=models.CASCADE,
        related_name="historico",
    )
    etapa = models.ForeignKey(
        ExecucaoEtapaProducao,
        on_delete=models.SET_NULL,
        related_name="historico",
        null=True,
        blank=True,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="historico_producao",
        null=True,
        blank=True,
    )
    evento = models.CharField(max_length=20, choices=Evento.choices)
    status_anterior = models.CharField(max_length=20, blank=True)
    status_novo = models.CharField(max_length=20, blank=True)
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.ordem_producao} · {self.get_evento_display()}"

    class Meta:
        verbose_name = "Histórico de produção"
        verbose_name_plural = "Históricos de produção"
        ordering = ("-criacao", "-id")


# ======================================================================
# ORÇAMENTOS
# ======================================================================
# Letras e números, e SÓ letras e números. A ausência do "_" e do "-" é o
# ponto do alfabeto, não um detalhe de estilo -- ver gerar_token_orcamento.
ALFABETO_DO_TOKEN = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
)

TAMANHO_DO_TOKEN = 32


def gerar_token_orcamento():
    """Chave da página que o cliente abre.

    32 caracteres sorteados de um alfabeto de 62 dão ~190 bits. É o que
    substitui uma senha: a página pública é aberta por quem tiver o link,
    então o link precisa ser impossível de adivinhar. Sequencial ou UUID1
    não serviriam -- de um orçamento se chegaria ao do concorrente.

    POR QUE NÃO `secrets.token_urlsafe`. Ele sorteia também "_" e "-", e
    era o que quebrava a proposta no WhatsApp: o aplicativo trata "_" como
    marca de itálico, e um token como `_uYep...PBTrD` chegava do outro
    lado em itálico e SEM os sublinhados -- o cliente clicava e caía num
    404. O mesmo vale para colar o link em qualquer conversa que formate
    texto. Trocar o alfabeto resolve na origem, e sem tocar em nada: os
    tokens antigos continuam valendo, porque o campo só guarda texto.
    """
    return "".join(
        secrets.choice(ALFABETO_DO_TOKEN) for _ in range(TAMANHO_DO_TOKEN)
    )


class Orcamento(Prime):
    """Proposta comercial montada no painel interno."""

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        AGUARDANDO_RESPOSTA = "aguardando_resposta", "Aguardando resposta"
        EM_NEGOCIACAO = "em_negociacao", "Em negociação"
        APROVADO = "aprovado", "Aprovado"
        RECUSADO = "recusado", "Recusado"
        EXPIRADO = "expirado", "Expirado"
        SUBSTITUIDO = "substituido", "Substituído por nova versão"

    class StatusPagamento(models.TextChoices):
        PENDENTE = "pendente", "Pagamento pendente"
        PARCIAL = "parcial", "Pagamento parcial"
        PAGO = "pago", "Pago"
        ESTORNADO = "estornado", "Estornado"

    class Origem(models.TextChoices):
        INTERNO = "interno", "Atendimento interno"
        AMBULANTE = "ambulante", "Vendedor ambulante"

    #: Situações em que a proposta ainda está viva e pode receber resposta.
    EM_ABERTO = (
        Status.RASCUNHO,
        Status.AGUARDANDO_RESPOSTA,
        Status.EM_NEGOCIACAO,
    )
    #: Situações em que o cliente já respondeu -- não se responde de novo.
    RESPONDIDO = (Status.APROVADO, Status.RECUSADO)

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        related_name="orcamentos",
        null=True,
        blank=True,
    )
    # Orçamento de balcão costuma nascer antes do cadastro do cliente.
    nome_cliente = models.CharField(max_length=120, blank=True)
    contato = models.CharField(max_length=120, blank=True)
    whatsapp_cliente = models.CharField(
        "WhatsApp do cliente",
        max_length=24,
        blank=True,
        help_text="Número com DDD usado no envio da proposta.",
    )
    email_cliente = models.EmailField(
        "E-mail do cliente",
        blank=True,
        help_text="Endereço que recebe a proposta comercial.",
    )

    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.RASCUNHO,
        db_index=True,
    )
    origem = models.CharField(
        "Origem comercial",
        max_length=20,
        choices=Origem.choices,
        default=Origem.INTERNO,
        db_index=True,
        help_text=(
            "Preenchida automaticamente pela função de quem criou a proposta."
        ),
    )
    validade = models.DateField(
        "Válido até",
        null=True,
        blank=True,
        help_text=(
            "Proposta nova nasce com 5 dias. Data anterior a hoje não é "
            "aceita: seria enviar ao cliente um documento já vencido."
        ),
    )
    desconto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    frete = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    forma_pagamento = models.CharField(
        "Forma de pagamento",
        max_length=120,
        blank=True,
        help_text="Ex.: Pix, boleto, 50% na entrada e 50% na entrega.",
    )
    forma_envio = models.CharField(
        "Forma de envio",
        max_length=120,
        blank=True,
        help_text="Ex.: retirada, transportadora ou entrega Lazer & Sport.",
    )
    observacoes = models.TextField(blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="orcamentos",
        null=True,
        blank=True,
    )

    # ---------------- histórico de negociação ----------------
    # Proposta enviada nunca volta a ser um arquivo editável. Quando o
    # cliente pede desconto ou troca de item, nasce outra versão e esta
    # continua intacta como prova do que foi apresentado naquele momento.
    orcamento_anterior = models.OneToOneField(
        "self",
        on_delete=models.SET_NULL,
        related_name="orcamento_refeito",
        null=True,
        blank=True,
    )
    versao = models.PositiveIntegerField(default=1)
    motivo_negociacao = models.TextField(blank=True)

    # ---------------- pagamento ----------------
    status_pagamento = models.CharField(
        max_length=12,
        choices=StatusPagamento.choices,
        default=StatusPagamento.PENDENTE,
        db_index=True,
    )
    valor_pago = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    pago_em = models.DateTimeField(null=True, blank=True)
    observacao_pagamento = models.CharField(max_length=240, blank=True)

    # ---------------- página que o cliente abre ----------------
    token = models.CharField(
        max_length=64,
        unique=True,
        default=gerar_token_orcamento,
        editable=False,
        db_index=True,
        help_text="Chave do link público. Não aparece em nenhuma tela interna.",
    )
    enviado_em = models.DateTimeField(null=True, blank=True)
    respondido_em = models.DateTimeField(null=True, blank=True)
    respondido_por = models.CharField(
        max_length=120,
        blank=True,
        help_text="Nome que o cliente digitou ao aprovar ou recusar.",
    )
    motivo_recusa = models.TextField(
        blank=True,
        help_text="O que o cliente escreveu ao recusar, quando escreveu.",
    )

    @property
    def destinatario(self):
        if self.cliente:
            return self.cliente.nome_cliente
        return self.nome_cliente or "Sem cliente"

    @property
    def whatsapp_destinatario(self):
        """Canal explícito, com compatibilidade para propostas antigas."""
        if self.whatsapp_cliente:
            return self.whatsapp_cliente
        if (
            self.cliente_id
            and self.cliente
            and self.cliente.telefone
            and self.cliente.canal_telefone == Cliente.CanalTelefone.WHATSAPP
        ):
            return self.cliente.telefone
        return self.contato if "@" not in (self.contato or "") else ""

    @property
    def email_destinatario(self):
        """E-mail explícito, com compatibilidade para propostas antigas."""
        if self.email_cliente:
            return self.email_cliente
        if self.cliente_id and self.cliente and self.cliente.email:
            return self.cliente.email
        return self.contato if "@" in (self.contato or "") else ""

    @property
    def subtotal(self):
        return sum(
            (item.subtotal for item in self.itens.all()),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))

    @property
    def total(self):
        bruto = self.subtotal + (self.frete or Decimal("0.00"))
        liquido = bruto - (self.desconto or Decimal("0.00"))
        # Desconto maior que o total viraria um orçamento negativo.
        return max(liquido, Decimal("0.00")).quantize(Decimal("0.01"))

    #: Prazo com que uma proposta nova nasce, em dias corridos.
    #:
    #: Cinco dias é uma decisão comercial, não um número técnico: é o
    #: prazo que a fábrica consegue segurar preço de material e agenda de
    #: montagem. Antes o campo vinha vazio, e proposta sem prazo não entra
    #: na fila de cobrança da central de avisos -- ela ficava esperando
    #: uma resposta que ninguém ia cobrar. Quem precisar de outro prazo
    #: troca no campo; quem não pensar no assunto sai com um prazo válido.
    DIAS_DE_VALIDADE_PADRAO = 5

    @classmethod
    def validade_padrao(cls):
        return timezone.localdate() + timedelta(days=cls.DIAS_DE_VALIDADE_PADRAO)

    @property
    def vencido(self):
        return bool(
            self.validade
            and self.validade < timezone.localdate()
            and self.status in self.EM_ABERTO
        )

    @property
    def publicado(self):
        """A página do cliente já existe para esta proposta?

        A view pública recusa rascunho com 404 -- de propósito: enquanto a
        equipe monta a proposta, quem tiver o link não deve ver nada. O
        problema é que o painel entregava o endereço mesmo assim, e a
        janela de envio já abria com o botão "Abrir" apontando para ele.
        Quem conferia antes de enviar levava uma página de erro no rosto,
        e a leitura óbvia era "o sistema quebrou".

        Esta propriedade é a MESMA regra da view pública, dita num lugar
        só. Quem for mostrar o link pergunta aqui primeiro.
        """
        return self.status != self.Status.RASCUNHO

    @property
    def pode_enviar(self):
        """Ainda faz sentido mandar (ou remandar) esta proposta ao cliente?

        VENCIDA NÃO GERA MAIS LINK. O link leva a uma página que anuncia
        "proposta expirada": mandar isso ao cliente é pior do que não
        mandar nada -- e a equipe fazia, porque o botão continuava lá
        igual ao das propostas vivas. Para uma proposta que passou do
        prazo o caminho é `Refazer`, que cria a versão nova com o preço
        de hoje.

        Substituída e respondida também saem: a primeira foi trocada por
        outra versão, e a segunda o cliente já respondeu -- reenviar
        pediria uma decisão que já foi tomada.
        """
        if self.vencido:
            return False
        return self.status in (
            self.Status.RASCUNHO,
            self.Status.AGUARDANDO_RESPOSTA,
            self.Status.EM_NEGOCIACAO,
        )

    @property
    def pode_receber_pagamento(self):
        """Falta dinheiro a registrar nesta proposta?

        Proposta quitada não mostra "Pagamento". O botão continuava ali
        depois de paga, e apertar abria uma janela pedindo um valor que
        já estava lá -- a leitura era "será que não registrou?". Quitada,
        o que a tela tem de fazer é DIZER que está quitada.
        """
        return (
            self.status == self.Status.APROVADO
            and self.status_pagamento != self.StatusPagamento.PAGO
        )

    @property
    def quitado(self):
        return self.status_pagamento == self.StatusPagamento.PAGO

    @property
    def pode_refazer(self):
        """Vale criar uma versão nova a partir desta?

        Só o que já saiu do rascunho e ainda não foi substituído. É o
        caminho da proposta vencida, da recusada e da que voltou para
        negociação.

        A QUITADA FICA DE FORA. Refazer marca a atual como substituída,
        e substituir um documento contra o qual o dinheiro já entrou é
        apagar o papel que justifica o valor recebido. Se o cliente quer
        outra coisa depois de pagar, isso é uma proposta nova -- não uma
        versão desta.

        A QUE JÁ VIROU O.S. TAMBÉM FICA DE FORA, e por isto o servidor
        conferia à parte: a proposta que liberou execução fica congelada
        junto com ela. Agora a regra inteira mora aqui, e a tela e o
        servidor perguntam à mesma propriedade -- era possível esconder o
        botão e ainda assim aceitar o POST.
        """
        return bool(
            self.pk
            and not self.pode_editar
            and not self.quitado
            and self.status != self.Status.SUBSTITUIDO
            and not hasattr(self, "orcamento_refeito")
            and not hasattr(self, "ordem_servico")
        )

    @property
    def recusada(self):
        """O cliente disse não -- pela página dele ou pelo telefone.

        As duas recusas valem o mesmo: em ambas existe uma negociação
        viva que precisa de outra proposta. O que mudava era a qualidade
        do registro -- a recusa pelo site guardava motivo, autor e
        instante; a verbal guardava só o carimbo "Recusado". Ver
        `registrar_recusa`.
        """
        return self.status == self.Status.RECUSADO

    @property
    def motivo_da_proxima_versao(self):
        """O que a versão seguinte precisa resolver, em uma frase.

        Refazer criava um rascunho limpo, sem memória nenhuma do que o
        cliente tinha objetado. Quem ajustava o preço abria a proposta
        nova sem saber se o problema era preço, prazo ou escopo -- e ia
        perguntar de novo ao colega, ou ao cliente.
        """
        return (self.motivo_recusa or self.motivo_negociacao or "").strip()

    def registrar_recusa(self, motivo="", por="", quando=None):
        """Carimba a recusa com motivo, autor e instante.

        A recusa que chega pela página do cliente já preenchia os três.
        A verbal -- que é a mais comum, porque o cliente responde por
        telefone ou no balcão -- só mudava o status: a proposta ficava
        "Recusada" sem dizer por quem nem por quê, e a versão seguinte
        nascia às cegas. Os dois caminhos passam por aqui.
        """
        self.status = self.Status.RECUSADO
        if motivo:
            self.motivo_recusa = motivo
        if por:
            self.respondido_por = por
        self.respondido_em = quando or timezone.now()
        self.save(update_fields=[
            "status", "motivo_recusa", "respondido_por",
            "respondido_em", "atualizado",
        ])

    @property
    def dias_para_vencer(self):
        """Quantos dias faltam para a validade. Negativo já passou.

        None quando não há validade -- que é diferente de "vence hoje", e
        é por isso que a central de avisos precisa distinguir os dois.
        """
        if not self.validade:
            return None
        return (self.validade - timezone.localdate()).days

    @property
    def respondido(self):
        return self.status in self.RESPONDIDO

    @property
    def pode_editar(self):
        """Somente rascunho é mutável; negociação gera uma nova versão."""
        return self.status == self.Status.RASCUNHO

    @property
    def saldo_pagamento(self):
        return max(
            self.total - (self.valor_pago or Decimal("0.00")),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))

    @property
    def grupo_versoes_id(self):
        atual = self
        while atual.orcamento_anterior_id:
            atual = atual.orcamento_anterior
        return atual.pk

    def cadeia_de_versoes(self):
        """Todas as versões desta negociação, da primeira à atual.

        O HISTÓRICO EXISTIA E NÃO APARECIA EM LUGAR NENHUM.

        `orcamento_anterior` já ligava uma versão à outra desde que
        Refazer foi criado, mas nada na tela lia essa corrente. Na lista,
        as substituídas estão escondidas de propósito -- misturar as duas
        faz a mesma negociação parecer três orçamentos. O efeito
        colateral era que elas sumiam por inteiro: quem abria a proposta
        atual não tinha como ver o que foi oferecido antes, nem por quê,
        justamente quando o cliente liga perguntando pelo preço antigo.

        Aqui a corrente é percorrida para trás até a primeira versão e
        devolvida em ordem. O limite existe porque isto é uma sequência
        de consultas, uma por elo: uma negociação com dez idas e vindas é
        muito; com cinquenta, é dado corrompido, e não histórico.
        """
        cadeia = []
        atual = self
        while atual and len(cadeia) < 50:
            cadeia.append(atual)
            atual = atual.orcamento_anterior if atual.orcamento_anterior_id else None
        cadeia.reverse()
        return cadeia

    @property
    def caminho_publico(self):
        """Caminho da página do cliente, sem domínio.

        Sem domínio de propósito: o painel interno roda em
        interno.lazersport.com.br e a página do cliente mora no site
        principal. Quem monta o endereço completo é quem sabe qual é o
        site -- ver `endereco_do_site` em utils.

        O urlconf é passado NA MÃO, e isso não é firula. Num pedido que
        chega pelo subdomínio interno, o SubdomainURLMiddleware troca o
        urlconf do request para sistema_interno.urls, e o reverse passa a
        enxergar só as rotas do painel. A rota pública mora no urlconf
        raiz: sem apontar para ele, este reverse levanta NoReverseMatch
        exatamente onde mais importa -- na hora de gerar o link para o
        cliente, de dentro do painel.
        """
        from django.conf import settings
        from django.urls import reverse

        return reverse(
            "orcamento_publico",
            args=[self.token],
            urlconf=settings.ROOT_URLCONF,
        )

    @property
    def numero_documento(self):
        """Número legível no documento, estável e separado por ano."""
        ano = self.criacao.year if self.criacao else timezone.localdate().year
        return f"{(self.pk or 0):04d}/{ano}"

    def marcar_enviado(self):
        """Passa para "aguardando resposta" e carimba a hora, uma vez só.

        Reenviar não reescreve `enviado_em`: a data que interessa é a da
        primeira vez que a proposta saiu, que é de onde se conta há quanto
        tempo o cliente está com ela na mão.
        """
        alterado = []

        if self.status == self.Status.RASCUNHO:
            self.status = self.Status.AGUARDANDO_RESPOSTA
            alterado.append("status")

        if self.enviado_em is None:
            self.enviado_em = timezone.now()
            alterado.append("enviado_em")

        if alterado:
            self.save(update_fields=alterado)

        return bool(alterado)

    def registrar_pagamento(self, valor, observacao=""):
        """Atualiza o recebido e deriva a situação sem aceitar saldo negativo."""
        valor = max(Decimal(valor or 0), Decimal("0.00")).quantize(Decimal("0.01"))
        self.valor_pago = valor
        self.observacao_pagamento = (observacao or "").strip()[:240]
        if valor <= 0:
            self.status_pagamento = self.StatusPagamento.PENDENTE
            self.pago_em = None
        elif valor < self.total:
            self.status_pagamento = self.StatusPagamento.PARCIAL
            self.pago_em = None
        else:
            self.status_pagamento = self.StatusPagamento.PAGO
            self.pago_em = self.pago_em or timezone.now()
        self.save(update_fields=[
            "valor_pago", "status_pagamento", "pago_em",
            "observacao_pagamento", "atualizado",
        ])

    def registrar_resposta(self, aprovado, nome="", motivo=""):
        """Grava a decisão do cliente vinda da página pública."""
        self.status = self.Status.APROVADO if aprovado else self.Status.RECUSADO
        self.respondido_em = timezone.now()
        self.respondido_por = (nome or "").strip()[:120]
        self.motivo_recusa = "" if aprovado else (motivo or "").strip()
        self.save(
            update_fields=[
                "status",
                "respondido_em",
                "respondido_por",
                "motivo_recusa",
            ]
        )
        if aprovado:
            self.sincronizar_cliente_aprovado()

    def sincronizar_cliente_aprovado(self):
        """Proposta fechada põe o cliente no mapa do site.

        Antes esta chamada COPIAVA o cadastro para uma segunda tabela, a da
        vitrine, e o trabalho era manter as duas cópias parecidas. Não há
        mais duas: publicar virou ligar uma chave no próprio cliente.
        """
        if self.status != self.Status.APROVADO or not self.cliente_id:
            return None

        # Import local evita ciclo: clientes importa os modelos para gravar
        # endereço e orçamento importa o serviço apenas neste fluxo.
        from .clientes import publicar_no_mapa

        return publicar_no_mapa(self.cliente)

    def __str__(self):
        return f"Orçamento #{self.pk} — {self.destinatario}"

    class Meta:
        verbose_name = "Orçamento"
        verbose_name_plural = "Orçamentos"
        ordering = ("-criacao", "-id")
        indexes = [
            models.Index(
                fields=("status", "validade"),
                name="orc_status_validade_idx",
            ),
        ]


class AceiteOrcamento(models.Model):
    """Comprovante imutável do aceite eletrônico de uma proposta.

    Não guarda IP nem navegador em texto. Essas informações são
    transformadas em HMAC no momento do aceite: continuam úteis para
    demonstrar que duas respostas vieram do mesmo contexto, sem criar um
    cadastro paralelo de dados pessoais sensíveis.
    """

    orcamento = models.OneToOneField(
        Orcamento,
        on_delete=models.PROTECT,
        related_name="aceite_eletronico",
    )
    codigo_publico = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    assinante_nome = models.CharField(max_length=120)
    assinante_documento = models.CharField(max_length=14)
    consentimento = models.BooleanField(default=True)
    proposta_hash = models.CharField(max_length=64)
    ip_hash = models.CharField(max_length=64)
    navegador_hash = models.CharField(max_length=64)
    termos_versao = models.CharField(max_length=20, default="2026-08")
    assinado_em = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("O comprovante de aceite é imutável.")
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Aceite eletrônico de orçamento"
        verbose_name_plural = "Aceites eletrônicos de orçamentos"
        ordering = ("-assinado_em",)

    def __str__(self):
        return f"Aceite {self.codigo_publico}"


class AvaliacaoBlocoOrcamento(Prime):
    """Decisão do superadministrador sobre cada responsabilidade da proposta."""

    class Bloco(models.TextChoices):
        COMERCIAL = "comercial", "Comercial"
        FINANCEIRO = "financeiro", "Financeiro"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADO = "aprovado", "Aprovado"
        AJUSTES = "ajustes", "Requer ajustes"

    orcamento = models.ForeignKey(
        Orcamento,
        on_delete=models.CASCADE,
        related_name="avaliacoes_blocos",
    )
    bloco = models.CharField(max_length=12, choices=Bloco.choices)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
    )
    observacao = models.TextField(blank=True)
    avaliador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="avaliacoes_blocos_orcamento",
        null=True,
        blank=True,
    )
    avaliado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Avaliação de bloco do orçamento"
        verbose_name_plural = "Avaliações dos blocos dos orçamentos"
        ordering = ("orcamento_id", "bloco")
        constraints = [
            models.UniqueConstraint(
                fields=("orcamento", "bloco"),
                name="uniq_avaliacao_bloco_orcamento",
            ),
        ]

    def __str__(self):
        return (
            f"Orçamento #{self.orcamento_id} · "
            f"{self.get_bloco_display()} · {self.get_status_display()}"
        )


class AvaliacaoSetor(Prime):
    """Nota periódica e comentário do superadministrador por setor."""

    class Setor(models.TextChoices):
        PRODUCAO = "producao", "Produção"
        CRIACAO = "criacao", "Criação e site"
        VENDAS = "vendas", "Vendas internas"
        AMBULANTE = "ambulante", "Vendedores ambulantes"
        FINANCEIRO = "financeiro", "Financeiro"
        GESTAO = "gestao", "Gestão"

    setor = models.CharField(max_length=16, choices=Setor.choices, db_index=True)
    periodo = models.DateField(
        db_index=True,
        help_text="Primeiro dia do mês avaliado.",
    )
    nota = models.PositiveSmallIntegerField(
        validators=(MinValueValidator(1), MaxValueValidator(5)),
    )
    observacao = models.TextField(blank=True)
    avaliador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="avaliacoes_setores",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Avaliação de setor"
        verbose_name_plural = "Avaliações dos setores"
        ordering = ("-periodo", "setor")
        constraints = [
            models.UniqueConstraint(
                fields=("setor", "periodo"),
                name="uniq_avaliacao_setor_periodo",
            ),
        ]

    def __str__(self):
        return f"{self.get_setor_display()} · {self.periodo:%m/%Y} · nota {self.nota}"


class EnvioOrcamento(Prime):
    """Cada tentativa de mandar a proposta para o cliente.

    POR QUE GUARDAR ISTO. "O cliente disse que não recebeu" é a frase mais
    comum do comercial, e sem registro ninguém sabe responder: saiu? para
    qual endereço? deu erro? Com o histórico, a resposta está na tela --
    inclusive o motivo exato quando o servidor de e-mail recusou.

    Falha também vira registro. Uma tentativa que deu errado é justamente
    a que precisa aparecer.
    """

    class Canal(models.TextChoices):
        LINK = "link", "Link copiado"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "E-mail"

    orcamento = models.ForeignKey(
        "Orcamento",
        on_delete=models.CASCADE,
        related_name="envios",
    )
    canal = models.CharField(max_length=10, choices=Canal.choices, db_index=True)
    destino = models.CharField(
        max_length=254,
        blank=True,
        help_text="Telefone ou e-mail para onde a proposta foi mandada.",
    )
    sucesso = models.BooleanField(default=True)
    detalhe = models.CharField(
        max_length=240,
        blank=True,
        help_text="Motivo da falha, quando houve.",
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="envios_orcamento",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Envio de orçamento"
        verbose_name_plural = "Envios de orçamento"
        ordering = ("-criacao", "-id")

    def __str__(self):
        estado = "ok" if self.sucesso else "falhou"
        return f"#{self.orcamento_id} · {self.get_canal_display()} · {estado}"


class AtividadeOrcamento(Prime):
    """Movimentação comercial que precisa aparecer aos outros usuários.

    A proposta em si guarda o estado atual; esta tabela guarda o acontecimento.
    Sem esse rastro, dois usuários com o painel aberto enxergam apenas números
    agregados e a criação de um rascunho não muda aviso nenhum. O autor fica
    registrado para que o próprio trabalho não volte como uma notificação para
    quem acabou de executá-lo.
    """

    class Tipo(models.TextChoices):
        CRIADO = "criado", "criou"
        ALTERADO = "alterado", "alterou"
        SITUACAO = "situacao", "mudou a situação de"
        REFEITO = "refeito", "criou uma nova versão de"
        PAGAMENTO = "pagamento", "atualizou o pagamento de"
        AVALIACAO = "avaliacao", "avaliou"
        ENVIADO = "enviado", "preparou o envio de"

    orcamento = models.ForeignKey(
        Orcamento,
        on_delete=models.SET_NULL,
        related_name="atividades",
        null=True,
        blank=True,
    )
    orcamento_numero = models.PositiveIntegerField(db_index=True)
    cliente = models.CharField(max_length=120, blank=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="atividades_orcamento",
        null=True,
        blank=True,
    )
    autor_nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=16, choices=Tipo.choices, db_index=True)
    resumo = models.CharField(max_length=240, blank=True)

    @classmethod
    def registrar(cls, orcamento, autor, tipo, resumo=""):
        """Cria um evento curto, suficiente para o sino explicar a mudança."""
        nome = "Sistema"
        if getattr(autor, "is_authenticated", False):
            nome = autor.get_full_name() or autor.get_username()
        return cls.objects.create(
            orcamento=orcamento,
            orcamento_numero=orcamento.pk,
            cliente=orcamento.destinatario[:120],
            autor=autor if getattr(autor, "is_authenticated", False) else None,
            autor_nome=nome[:150],
            tipo=tipo,
            resumo=(resumo or "")[:240],
        )

    class Meta:
        verbose_name = "Atividade de orçamento"
        verbose_name_plural = "Atividades de orçamentos"
        ordering = ("-criacao", "-id")
        indexes = [
            models.Index(
                fields=("orcamento", "-id"),
                name="atividade_orcamento_idx",
            ),
        ]

    def __str__(self):
        return f"{self.autor_nome} {self.get_tipo_display()} #{self.orcamento_numero}"


class ItemOrcamento(Prime):
    orcamento = models.ForeignKey(
        Orcamento,
        on_delete=models.CASCADE,
        related_name="itens",
    )
    # A descrição é gravada mesmo quando há item associado: se o cadastro
    # mudar de nome depois, a proposta enviada ao cliente continua valendo.
    descricao = models.CharField(max_length=180)

    # TRÊS ORIGENS, DE PROPÓSITO.
    #
    # `brinquedo` é o catálogo de verdade (core.Brinquedos) -- é dele que
    # sai quase todo orçamento, porque é o que a empresa aluga e vende, e
    # é o que traz foto, medidas e preço para a página do cliente.
    #
    # `produto` é o que a fábrica monta (ProdutoInterno). Continua aqui
    # porque nem tudo que se orça está no catálogo: máquina, peça avulsa,
    # serviço. Remover o campo apagaria o vínculo dos orçamentos antigos.
    #
    # `peca` é o catálogo de reposição da loja. Mantê-la como vínculo real
    # traz foto e preço para a proposta e evita digitar a mesma mola, lona
    # ou rede como linha solta em toda venda.
    #
    # Uma linha usa uma origem, nunca várias -- ver `clean`.
    brinquedo = models.ForeignKey(
        Brinquedos,
        on_delete=models.SET_NULL,
        related_name="itens_orcamento",
        null=True,
        blank=True,
        help_text="Item do catálogo do site.",
    )
    produto = models.ForeignKey(
        ProdutoInterno,
        on_delete=models.SET_NULL,
        related_name="itens_orcamento",
        null=True,
        blank=True,
        help_text="Item de produção, quando não está no catálogo.",
    )
    peca = models.ForeignKey(
        PecasReposicao,
        on_delete=models.SET_NULL,
        related_name="itens_orcamento",
        null=True,
        blank=True,
        help_text="Peça de reposição do catálogo da loja.",
    )
    quantidade = models.PositiveIntegerField(default=1)
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    @property
    def subtotal(self):
        return (self.valor_unitario * self.quantidade).quantize(Decimal("0.01"))

    @property
    def imagem(self):
        """Foto para a página do cliente, quando o item veio do catálogo.

        Item de produção e linha escrita à mão não têm foto, e a página
        precisa saber disso para desenhar o lugar da imagem de outro jeito
        em vez de deixar um buraco.

        DUAS GAVETAS PARA A FOTO DO BRINQUEDO, e é preciso olhar as duas.
        `imagem_brinquedo` é o campo antigo; a galeria tipada
        (`imagem_perfil`) é onde o cadastro rápido guarda. Um brinquedo
        criado de dentro do orçamento com foto de VERSO -- e sem a de
        frente -- não preenchia o campo antigo, e a proposta saía sem
        imagem embora o cadastro tivesse fotos.
        """
        if self.brinquedo_id and self.brinquedo:
            if self.brinquedo.imagem_brinquedo:
                return self.brinquedo.imagem_brinquedo
            capa = self.brinquedo.imagem_perfil
            if capa and getattr(capa, "imagem", None):
                return capa.imagem
            # `.all()` e a ordenação em Python de propósito: a página do
            # cliente traz as fotos por prefetch, e um `order_by` aqui
            # ignoraria esse cache -- uma consulta por linha da proposta,
            # que é exatamente o que o prefetch existe para evitar.
            fotos = sorted(
                self.brinquedo.imagens_brinquedo.all(),
                key=lambda foto: (foto.ordem or 0, foto.id),
            )
            for foto in fotos:
                if foto.imagem:
                    return foto.imagem
        if self.peca_id and self.peca:
            imagem = self.peca.imagem_principal
            if imagem and imagem.imagem:
                return imagem.imagem
        return None

    @property
    def ficha(self):
        """As linhas de detalhe que o documento imprime abaixo do nome.

        POR QUE ELAS VÊM DO CADASTRO, e não da descrição digitada. A
        linha da proposta tem 180 caracteres e é o texto comercial ("2
        dias de locação, montagem inclusa"). Medida, voltagem e o que o
        brinquedo é continuam no catálogo -- e era exatamente isso que
        sumia na impressão: o cliente recebia "Piscina de bolinhas" sem
        saber o tamanho da piscina.

        Só entra o que EXISTE no cadastro. Item escrito à mão não ganha
        linha nenhuma, e a proposta continua com a cara de sempre.
        """
        origem = self.brinquedo or self.peca or self.produto
        if origem is None:
            return []

        linhas = []
        descricao = (
            getattr(origem, "descricao", "")
            or getattr(origem, "descricao_peca", "")
            or ""
        ).strip()
        # A descrição do catálogo repetindo a linha da proposta seria
        # ruído: o cliente leria a mesma frase duas vezes.
        if descricao and descricao.strip().lower() != (self.descricao or "").strip().lower():
            linhas.append(descricao)

        medidas = getattr(origem, "dimensoes_m", None)
        if medidas:
            linhas.append(medidas)

        voltagem = (getattr(origem, "voltz", "") or "").strip()
        if voltagem:
            linhas.append(f"Voltagem: {voltagem}")

        return linhas

    def clean(self):
        from django.core.exceptions import ValidationError

        origens = sum(bool(valor) for valor in (
            self.brinquedo_id,
            self.produto_id,
            self.peca_id,
        ))
        if origens > 1:
            raise ValidationError(
                "Um item vem do catálogo, da produção ou das peças, nunca de mais de uma origem."
            )

    def __str__(self):
        return self.descricao

    class Meta:
        verbose_name = "Item do orçamento"
        verbose_name_plural = "Itens do orçamento"
        ordering = ("id",)


# ======================================================================
# ORDENS DE SERVIÇO
# ======================================================================
class OrdemServico(Prime):
    """Execução operacional separada da proposta comercial.

    Orçamento responde *quanto custa e se o cliente aprova*. A ordem de
    serviço responde *o que aconteceu com o equipamento, quem executou e
    quando foi entregue*. Os dois documentos podem ter itens e valores,
    mas não compartilham situação nem histórico: transformar a proposta
    em ficha técnica apagaria a decisão comercial original.

    Uma O.S. pode nascer de um chamado público de manutenção, mas também
    pode registrar instalação, revisão, visita técnica ou outro serviço
    prestado diretamente pela equipe.
    """

    class Tipo(models.TextChoices):
        MANUTENCAO = "manutencao", "Manutenção"
        INSTALACAO = "instalacao", "Instalação"
        REVISAO = "revisao", "Revisão preventiva"
        VISITA = "visita", "Visita técnica"
        OUTRO = "outro", "Outro serviço"

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        AGUARDANDO_RESPOSTA = "aguardando_resposta", "Aguardando ciência"
        ABERTA = "aberta", "Aberta"
        AGENDADA = "agendada", "Agendada"
        EM_EXECUCAO = "em_execucao", "Em execução"
        AGUARDANDO_PECA = "aguardando_peca", "Aguardando peça"
        CONCLUIDA = "concluida", "Concluída"
        CANCELADA = "cancelada", "Cancelada"
        SUBSTITUIDA = "substituida", "Substituída por nova versão"

    class Prioridade(models.TextChoices):
        BAIXA = "baixa", "Baixa"
        NORMAL = "normal", "Normal"
        ALTA = "alta", "Alta"
        URGENTE = "urgente", "Urgente"

    class StatusPagamento(models.TextChoices):
        PENDENTE = "pendente", "Pagamento pendente"
        PARCIAL = "parcial", "Pagamento parcial"
        PAGO = "pago", "Pago"
        ESTORNADO = "estornado", "Estornado"

    ABERTAS = (
        Status.AGUARDANDO_RESPOSTA,
        Status.ABERTA,
        Status.AGENDADA,
        Status.EM_EXECUCAO,
        Status.AGUARDANDO_PECA,
    )
    #: Fila mostrada no número do menu. Rascunho também é trabalho ainda
    #: não finalizado; concluída, cancelada e substituída já saíram dela.
    PENDENTES = (Status.RASCUNHO,) + ABERTAS
    #: Situações em que a O.S. já saiu de cena e a lista não a mostra de
    #: primeira. Ver `OrdensServicoInnerView.get`.
    ARQUIVADAS = (Status.SUBSTITUIDA,)
    #: O serviço ainda não começou: a data marcada é promessa, e não
    #: histórico. É nestas situações que a agenda vencida invalida o
    #: documento. Ver `agenda_vencida`.
    AGUARDANDO_A_DATA = (
        Status.RASCUNHO,
        Status.AGUARDANDO_RESPOSTA,
        Status.ABERTA,
        Status.AGENDADA,
    )

    # ================================================================
    # AS ETAPAS: O QUE SE SABE, E QUANDO
    # ================================================================
    # O FORMULÁRIO PEDIA TUDO NO PRIMEIRO SEGUNDO. Abrir uma O.S. de um
    # chamado que acabou de entrar mostrava, lado a lado, "defeito
    # relatado" e "serviço executado" -- e ninguém executou nada ainda.
    # Também pedia diagnóstico técnico antes de o técnico ver o
    # equipamento, e exigia ao menos um item antes de alguém saber que
    # peça vai ser usada.
    #
    # O efeito não é só feio. Campo que aparece antes da hora ensina duas
    # coisas erradas: que ele é opcional (porque fica em branco toda vez)
    # e que o formulário não sabe o que está fazendo. E quem preenche
    # alguma coisa ali para "não deixar vazio" está inventando: um
    # diagnóstico escrito antes da visita é um palpite que vai para o
    # documento do cliente com cara de laudo.
    #
    # Uma O.S. tem quatro momentos, e cada informação nasce em um deles.
    # A situação diz em qual a O.S. está -- é a mesma regra que já
    # governa as ações da lista, agora governando também os campos.
    class Etapa(models.TextChoices):
        ABERTURA = "abertura", "Abertura do chamado"
        AGENDA = "agenda", "Agendamento"
        EXECUCAO = "execucao", "Execução"
        ENTREGA = "entrega", "Entrega e cobrança"

    #: Ordem em que as etapas acontecem. Uma etapa "já chegou" quando a
    #: etapa da situação atual é ela ou uma posterior.
    SEQUENCIA_DE_ETAPAS = (
        Etapa.ABERTURA,
        Etapa.AGENDA,
        Etapa.EXECUCAO,
        Etapa.ENTREGA,
    )

    #: Até onde cada situação chegou.
    #
    #: CANCELADA fica em EXECUÇÃO, e não em ENTREGA: cancelar não entrega
    #: nada, mas o motivo do cancelamento quase sempre é o que se
    #: descobriu ao olhar o equipamento -- e esse texto é o diagnóstico.
    #:
    #: SUBSTITUÍDA fica em ENTREGA porque ela é histórico congelado: tudo
    #: o que ela chegou a ter precisa continuar visível ao ser aberta.
    ETAPA_DA_SITUACAO = {
        Status.RASCUNHO: Etapa.ABERTURA,
        Status.AGUARDANDO_RESPOSTA: Etapa.ABERTURA,
        Status.ABERTA: Etapa.ABERTURA,
        Status.AGENDADA: Etapa.AGENDA,
        Status.EM_EXECUCAO: Etapa.EXECUCAO,
        Status.AGUARDANDO_PECA: Etapa.EXECUCAO,
        Status.CANCELADA: Etapa.EXECUCAO,
        Status.CONCLUIDA: Etapa.ENTREGA,
        Status.SUBSTITUIDA: Etapa.ENTREGA,
    }

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        related_name="ordens_servico",
        null=True,
        blank=True,
    )
    orcamento = models.OneToOneField(
        Orcamento,
        on_delete=models.SET_NULL,
        related_name="ordem_servico",
        null=True,
        blank=True,
        help_text=(
            "Referência histórica da proposta que originou a execução. "
            "Situação, valores recebidos e envios não são sincronizados."
        ),
    )
    manutencao = models.ForeignKey(
        "core.Manutencao",
        on_delete=models.SET_NULL,
        related_name="ordens_servico",
        null=True,
        blank=True,
        help_text="Chamado que originou a O.S., quando houver.",
    )

    nome_cliente = models.CharField(max_length=120, blank=True)
    contato = models.CharField(max_length=120, blank=True)
    whatsapp_cliente = models.CharField(max_length=24, blank=True)
    email_cliente = models.EmailField(blank=True)
    endereco_servico = models.CharField(max_length=320, blank=True)

    tipo = models.CharField(
        max_length=16,
        choices=Tipo.choices,
        default=Tipo.MANUTENCAO,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RASCUNHO,
        db_index=True,
    )
    prioridade = models.CharField(
        max_length=10,
        choices=Prioridade.choices,
        default=Prioridade.NORMAL,
        db_index=True,
    )

    equipamento = models.CharField(max_length=180)
    numero_serie = models.CharField(max_length=80, blank=True)
    defeito_relatado = models.TextField(blank=True)
    diagnostico = models.TextField(blank=True)
    servico_executado = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    forma_pagamento = models.CharField(max_length=120, blank=True)
    frete = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    desconto = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    status_pagamento = models.CharField(
        max_length=12,
        choices=StatusPagamento.choices,
        default=StatusPagamento.PENDENTE,
        db_index=True,
    )
    valor_pago = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    pago_em = models.DateTimeField(null=True, blank=True)
    observacao_pagamento = models.CharField(max_length=240, blank=True)

    agendada_para = models.DateTimeField(null=True, blank=True, db_index=True)
    iniciada_em = models.DateTimeField(null=True, blank=True)
    concluida_em = models.DateTimeField(null=True, blank=True, db_index=True)
    garantia_ate = models.DateField(null=True, blank=True)

    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ordens_servico_tecnico",
        null=True,
        blank=True,
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ordens_servico_criadas",
        null=True,
        blank=True,
    )

    token = models.CharField(
        max_length=64,
        unique=True,
        default=gerar_token_orcamento,
        editable=False,
        db_index=True,
    )
    enviada_em = models.DateTimeField(null=True, blank=True)
    cliente_ciente_em = models.DateTimeField(null=True, blank=True)
    cliente_ciente_por = models.CharField(max_length=120, blank=True)

    # ---------------- histórico de execução ----------------
    # MESMO ESQUEMA DA PROPOSTA, PELO MESMO MOTIVO.
    #
    # A O.S. que o cliente já leu e assinou como ciente é o registro do
    # que foi combinado naquele dia: qual defeito, qual peça, quanto. Ao
    # abrir o equipamento o técnico descobre outra coisa -- era o motor,
    # não a lona -- e alguém precisava reescrever a O.S. por cima. O
    # papel que o cliente tinha na mão deixava de existir, e com ele a
    # explicação do valor que estava sendo cobrado.
    #
    # Refazer cria a versão seguinte e congela esta como SUBSTITUIDA. As
    # duas continuam consultáveis; só a atual aparece na lista.
    ordem_anterior = models.OneToOneField(
        "self",
        on_delete=models.SET_NULL,
        related_name="ordem_refeita",
        null=True,
        blank=True,
    )
    versao = models.PositiveIntegerField(default=1)
    motivo_refacao = models.TextField(
        blank=True,
        help_text="O que mudou em relação à versão anterior desta O.S.",
    )

    @property
    def destinatario(self):
        if self.cliente_id and self.cliente:
            return self.cliente.nome_cliente
        if self.nome_cliente:
            return self.nome_cliente
        if self.manutencao_id and self.manutencao:
            perfil = self.manutencao.usuario
            return (
                perfil.nome_completo
                or perfil.user.get_full_name()
                or perfil.user.username
            )
        return "Sem cliente"

    @property
    def whatsapp_destinatario(self):
        if self.whatsapp_cliente:
            return self.whatsapp_cliente
        if self.cliente_id and self.cliente and self.cliente.telefone:
            return self.cliente.telefone
        if self.manutencao_id and self.manutencao:
            return self.manutencao.telefone_contato or self.manutencao.usuario.telefone
        return ""

    @property
    def email_destinatario(self):
        if self.email_cliente:
            return self.email_cliente
        if self.cliente_id and self.cliente and self.cliente.email:
            return self.cliente.email
        if self.manutencao_id and self.manutencao:
            return self.manutencao.usuario.user.email or ""
        return ""

    @property
    def subtotal(self):
        return sum(
            (item.subtotal for item in self.itens.all()),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))

    @property
    def total(self):
        bruto = self.subtotal + (self.frete or Decimal("0.00"))
        liquido = bruto - (self.desconto or Decimal("0.00"))
        return max(liquido, Decimal("0.00")).quantize(Decimal("0.01"))

    @property
    def pode_receber_pagamento(self):
        """A cobrança só aparece enquanto ainda existe saldo válido.

        Substituída também sai: o dinheiro desta execução responde à
        versão que está valendo, e não à que foi congelada.
        """
        return (
            self.pk
            and self.status not in (
                self.Status.CANCELADA,
                self.Status.SUBSTITUIDA,
            )
            and self.status_pagamento != self.StatusPagamento.PAGO
            and self.total > Decimal("0.00")
        )

    @property
    def arquivada(self):
        """Versão congelada: existe no histórico, e não na fila de trabalho."""
        return self.status in self.ARQUIVADAS

    @property
    def etapa(self):
        """Até onde esta O.S. chegou. Ver `ETAPA_DA_SITUACAO`."""
        return self.ETAPA_DA_SITUACAO.get(self.status, self.Etapa.ABERTURA)

    @classmethod
    def etapa_alcancada(cls, situacao, etapa):
        """A O.S. nesta situação já passou por esta etapa?

        É o que decide se um bloco de campos aparece. `abertura` sempre
        aparece; `execucao` só a partir de "Em execução".
        """
        atual = cls.ETAPA_DA_SITUACAO.get(situacao, cls.Etapa.ABERTURA)
        sequencia = list(cls.SEQUENCIA_DE_ETAPAS)
        try:
            return sequencia.index(atual) >= sequencia.index(etapa)
        except ValueError:
            return True

    @property
    def registra_execucao(self):
        """Já dá para falar de diagnóstico e de peça consumida?"""
        return self.etapa_alcancada(self.status, self.Etapa.EXECUCAO)

    @property
    def pode_editar(self):
        """Uma versão substituída não volta a ser editável.

        Editar a versão que o cliente leu apagaria o papel que ele tem na
        mão. O que se edita é sempre a versão que está valendo.
        """
        return not self.arquivada

    @property
    def agenda_vencida(self):
        """A data marcada já passou e o serviço não andou?

        É a validade da O.S. O orçamento tem "Válido até"; a O.S. tem o
        compromisso de data, e é ele que envelhece. Uma O.S. marcada para
        a terça passada, ainda parada em "Agendada", é um documento que
        promete ao cliente um dia que não existe mais.

        Só conta enquanto o serviço não andou. Depois de entrar em
        execução ou de concluir, a data agendada vira histórico do que
        aconteceu, e histórico não vence -- reenviar o documento de um
        serviço já feito é legítimo, e acontece toda vez que o cliente
        pede a segunda via.
        """
        if not self.agendada_para:
            return False
        if self.status not in self.AGUARDANDO_A_DATA:
            return False
        return self.agendada_para < timezone.now()

    @property
    def pode_enviar(self):
        """Ainda faz sentido mandar (ou remandar) esta O.S. ao cliente?

        AS AÇÕES SÃO EM CIMA DA SITUAÇÃO -- a mesma regra da proposta.

        O botão de enviar ficava aceso em qualquer linha, cancelada e
        substituída incluídas. Mandar ao cliente o documento de um
        serviço que foi cancelado, ou a versão que já foi trocada por
        outra, é pedir que ele tome uma decisão sobre um papel que não
        vale mais.

        A AGENDA VENCIDA ENTRA NA MESMA REGRA. O orçamento já não sai
        depois de vencido, porque o cliente abriria uma página anunciando
        "proposta expirada". A O.S. parada numa data que passou tem o
        mesmo defeito, só que pior: o papel não avisa que está velho --
        ele afirma um compromisso. Reagende, e o botão volta.
        """
        return (
            not self.arquivada
            and self.status != self.Status.CANCELADA
            and not self.agenda_vencida
        )

    @property
    def motivo_de_nao_enviar(self):
        """Por que o botão de enviar não está aí. Em uma frase.

        Botão que some sem explicação vira chamado para o suporte: quem
        usa conclui que a tela quebrou, não que a regra mudou.
        """
        if self.arquivada:
            return "Esta versão foi substituída; envie a versão que está valendo."
        if self.status == self.Status.CANCELADA:
            return "O.S. cancelada não é enviada ao cliente."
        if self.agenda_vencida:
            return (
                "A data agendada já passou e o serviço não andou. "
                "Reagende antes de enviar."
            )
        return ''

    @property
    def pode_refazer(self):
        """Vale criar uma versão nova a partir desta?

        Só o que já saiu do rascunho -- rascunho ainda se edita no lugar,
        e criar versão dele seria criar histórico de um papel que nunca
        saiu da mesa.

        A QUITADA FICA DE FORA, como na proposta: refazer congela a
        atual, e congelar o documento contra o qual o dinheiro entrou é
        apagar o que justifica o valor recebido. Depois de paga, o que
        vier é uma O.S. nova.

        A cancelada também: ela não foi trocada por outra versão, foi
        encerrada. Recomeçar dali é abrir outra O.S.
        """
        return bool(
            self.pk
            and self.status not in (
                self.Status.RASCUNHO,
                self.Status.CANCELADA,
                self.Status.SUBSTITUIDA,
            )
            and not self.quitado
            and not hasattr(self, "ordem_refeita")
        )

    @property
    def quitado(self):
        return self.status_pagamento == self.StatusPagamento.PAGO

    @property
    def saldo_pagamento(self):
        return max(
            self.total - (self.valor_pago or Decimal("0.00")),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))

    @property
    def numero_documento(self):
        ano = self.criacao.year if self.criacao else timezone.localdate().year
        return f"OS-{(self.pk or 0):05d}/{ano}"

    @property
    def caminho_publico(self):
        from django.urls import reverse

        return reverse(
            "ordem_servico_publica",
            args=[self.token],
            urlconf=settings.ROOT_URLCONF,
        )

    @property
    def publicado(self):
        """Mesma pergunta do orçamento, mesma resposta: ver `Orcamento.publicado`.

        A view pública da O.S. recusa com 404 enquanto `enviada_em` for
        nula. O painel só mostra o link depois disso.
        """
        return bool(self.enviada_em)

    def cadeia_de_versoes(self):
        """Todas as versões desta O.S., da primeira à atual.

        Mesma corrente e mesmo motivo do orçamento (ver
        `Orcamento.cadeia_de_versoes`): a lista esconde as substituídas
        para não contar o mesmo serviço duas vezes, e escondido da lista
        não pode ser escondido do sistema. O limite é o mesmo -- uma
        O.S. com dez versões é muito; com cinquenta, é dado corrompido.
        """
        cadeia = []
        atual = self
        while atual and len(cadeia) < 50:
            cadeia.append(atual)
            atual = atual.ordem_anterior if atual.ordem_anterior_id else None
        cadeia.reverse()
        return cadeia

    @property
    def numero_com_versao(self):
        """`OS-00042/2026` na primeira versão, `... · v3` a partir da segunda.

        A versão só aparece quando existe: escrever "v1" em toda O.S.
        sugere um histórico que a maioria delas não tem.
        """
        if self.versao <= 1:
            return self.numero_documento
        return f"{self.numero_documento} · v{self.versao}"

    @property
    def cliente_ciente(self):
        return bool(self.cliente_ciente_em)

    def marcar_enviada(self):
        alterados = []
        if self.status == self.Status.RASCUNHO:
            self.status = self.Status.AGUARDANDO_RESPOSTA
            alterados.append("status")
        if self.enviada_em is None:
            self.enviada_em = timezone.now()
            alterados.append("enviada_em")
        if alterados:
            self.save(update_fields=[*alterados, "atualizado"])
        return bool(alterados)

    def registrar_ciencia(self, nome):
        if self.cliente_ciente_em:
            return False
        self.cliente_ciente_em = timezone.now()
        self.cliente_ciente_por = (nome or "").strip()[:120]
        alterados = ["cliente_ciente_em", "cliente_ciente_por", "atualizado"]
        if self.status == self.Status.AGUARDANDO_RESPOSTA:
            self.status = self.Status.ABERTA
            alterados.append("status")
        self.save(update_fields=alterados)
        return True

    def registrar_pagamento(self, valor, observacao=""):
        valor = max(Decimal(valor or 0), Decimal("0.00")).quantize(Decimal("0.01"))
        self.valor_pago = valor
        self.observacao_pagamento = (observacao or "").strip()[:240]
        if valor <= 0:
            self.status_pagamento = self.StatusPagamento.PENDENTE
            self.pago_em = None
        elif valor < self.total:
            self.status_pagamento = self.StatusPagamento.PARCIAL
            self.pago_em = None
        else:
            self.status_pagamento = self.StatusPagamento.PAGO
            self.pago_em = self.pago_em or timezone.now()
        self.save(update_fields=[
            "valor_pago", "status_pagamento", "pago_em",
            "observacao_pagamento", "atualizado",
        ])

    def __str__(self):
        return f"{self.numero_documento} — {self.destinatario}"

    class Meta:
        verbose_name = "Ordem de serviço"
        verbose_name_plural = "Ordens de serviço"
        ordering = ("-criacao", "-id")


class ItemOrdemServico(Prime):
    class Tipo(models.TextChoices):
        SERVICO = "servico", "Serviço / mão de obra"
        PECA = "peca", "Peça / material"
        DESLOCAMENTO = "deslocamento", "Deslocamento"
        OUTRO = "outro", "Outro"

    ordem = models.ForeignKey(
        OrdemServico,
        on_delete=models.CASCADE,
        related_name="itens",
    )
    tipo = models.CharField(
        max_length=14,
        choices=Tipo.choices,
        default=Tipo.SERVICO,
    )
    # A LINHA PODE VIR DO CATÁLOGO -- OU NÃO VIR DE LUGAR NENHUM.
    #
    # Metade do que entra numa O.S. não é item cadastrado: "trocar a lona
    # e recolar a emenda" é o serviço daquele dia, escrito à mão, e
    # obrigar um cadastro para ele encheria a tabela de peças de frases.
    # A outra metade É item: a bucha, o retentor, a peça de reposição que
    # a loja vende. Essa deve apontar para o cadastro, para o preço vir
    # certo e para a O.S. saber depois o que consumiu.
    #
    # Por isso o vínculo é opcional dos dois lados: `descricao` sempre
    # existe (é o que sai impresso), `peca` existe quando há de onde
    # puxar. É a versatilidade pedida -- item de manutenção ou peça
    # normal, na mesma linha.
    peca = models.ForeignKey(
        "core.PecasReposicao",
        on_delete=models.SET_NULL,
        related_name="itens_ordem_servico",
        null=True,
        blank=True,
        help_text="Peça da loja ou item de manutenção que originou a linha.",
    )
    descricao = models.CharField(max_length=200)
    quantidade = models.PositiveIntegerField(default=1)
    valor_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    @property
    def subtotal(self):
        return (self.quantidade * self.valor_unitario).quantize(Decimal("0.01"))

    def __str__(self):
        return self.descricao

    class Meta:
        verbose_name = "Item da ordem de serviço"
        verbose_name_plural = "Itens da ordem de serviço"
        ordering = ("id",)


class EnvioOrdemServico(Prime):
    class Canal(models.TextChoices):
        LINK = "link", "Link copiado"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "E-mail"

    ordem = models.ForeignKey(
        OrdemServico,
        on_delete=models.CASCADE,
        related_name="envios",
    )
    canal = models.CharField(max_length=10, choices=Canal.choices, db_index=True)
    destino = models.CharField(max_length=254, blank=True)
    sucesso = models.BooleanField(default=True)
    detalhe = models.CharField(max_length=240, blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="envios_ordem_servico",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Envio de ordem de serviço"
        verbose_name_plural = "Envios de ordens de serviço"
        ordering = ("-criacao", "-id")

    def __str__(self):
        estado = "ok" if self.sucesso else "falhou"
        return f"{self.ordem.numero_documento} · {self.get_canal_display()} · {estado}"


# ======================================================================
# NOTIFICAÇÃO NO CELULAR
# ======================================================================
class InscricaoPush(Prime):
    """O aparelho de uma pessoa, pronto para receber aviso.

    POR QUE UMA LINHA POR APARELHO, e não uma por pessoa: quem atende usa
    o celular na rua e o tablet na bancada, e o aviso precisa chegar nos
    dois. Trocar de aparelho não apaga o antigo -- quem apaga é o próprio
    serviço do fabricante, respondendo 404/410 na primeira tentativa
    depois de o aplicativo ser desinstalado (ver `push.InscricaoMorta`).

    O QUE ESTÁ GUARDADO AQUI. `endpoint` é o endereço no serviço do
    fabricante; `p256dh` e `auth` são as chaves públicas que o navegador
    gerou para este aparelho. Com elas se CIFRA a mensagem: quem tem o
    banco não lê aviso nenhum sem elas, e o serviço do fabricante nunca
    lê -- ele só entrega o pacote fechado.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inscricoes_push",
    )
    # O endpoint pode ser longo (o da Apple passa de 300 caracteres), e é
    # único: dois aparelhos nunca compartilham o mesmo.
    endpoint = models.CharField(max_length=600, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    #: Só para a pessoa se reconhecer na lista dos próprios aparelhos.
    aparelho = models.CharField(max_length=120, blank=True)
    ultimo_aviso = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Inscrição de notificação"
        verbose_name_plural = "Inscrições de notificação"
        ordering = ("-criacao", "-id")

    def __str__(self):
        return f"{self.usuario} · {self.aparelho or 'aparelho'}"


class AparelhoDoCliente(Prime):
    """O celular de quem baixou o aplicativo e aceitou receber aviso.

    IRMÃO DE `InscricaoPush`, E DE PROPÓSITO SEPARADO. Aquela é o
    aparelho da EQUIPE, e o que chega nela é trabalho: orçamento
    aprovado, estoque no fim, O.S. parada. Esta é o aparelho do CLIENTE,
    e o que chega é a loja falando com ele: promoção, brinquedo novo,
    aviso de entrega.

    Misturar as duas numa tabela só pareceria economia e seria um risco
    de todo dia: um `for aparelho in InscricaoPush.objects.all()` numa
    campanha mandaria o anúncio de Natal para o telefone do montador --
    e, pior, um aviso de operação para o cliente. São públicos
    diferentes, e público diferente é tabela diferente.

    SEM CONTA TAMBÉM VALE. Quem instalou o aplicativo e ainda não criou
    login é justamente quem mais precisa de um empurrão de volta. Por
    isso `usuario` aceita vazio: o que identifica o aparelho é o
    endereço de entrega, não a pessoa.
    """

    class Plataforma(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iPhone"
        OUTRO = "outro", "Outro aparelho"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="aparelhos_do_app",
        null=True,
        blank=True,
    )
    #: O endereço no serviço do fabricante. Ele É a credencial de entrega,
    #: e é único: dois aparelhos nunca compartilham o mesmo.
    endpoint = models.CharField(max_length=600, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    plataforma = models.CharField(
        max_length=10,
        choices=Plataforma.choices,
        default=Plataforma.OUTRO,
        db_index=True,
        help_text="Descoberto pelo próprio aparelho ao se inscrever.",
    )
    #: Só para a pessoa se reconhecer, e para a equipe entender a lista.
    aparelho = models.CharField(max_length=120, blank=True)
    ultimo_aviso = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Aparelho de cliente"
        verbose_name_plural = "Aparelhos de clientes"
        ordering = ("-criacao", "-id")

    def __str__(self):
        dono = self.usuario or "visitante"
        return f"{dono} · {self.get_plataforma_display()}"


class AvisoDoAplicativo(Prime):
    """A mensagem que a loja manda para o celular de quem baixou o app.

    NASCE RASCUNHO, E ISSO É A FEATURE. Notificação é a única coisa que
    a empresa escreve e não pode corrigir depois: ela chega no bolso de
    milhares de pessoas em segundos, e "ops, era 20%, não 200%" não tem
    conserto. Então o texto é escrito, salvo, relido, editado quantas
    vezes for preciso -- e só sai quando alguém aperta enviar.

    DEPOIS DE ENVIADO, VIRA HISTÓRICO. O texto de um aviso já entregue
    não é mais editável: o que está no celular das pessoas não muda, e
    deixar a linha mudar aqui faria o registro mentir sobre o que foi
    dito. Para mandar de novo com outra redação existe a cópia.
    """

    class Publico(models.TextChoices):
        TODOS = "todos", "Todos os aparelhos"
        ANDROID = "android", "Somente Android"
        IOS = "ios", "Somente iPhone"

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        ENVIADO = "enviado", "Enviado"

    #: Os limites são os do sistema operacional, não nossos: o Android
    #: corta o título por volta de 65 caracteres e o corpo por volta de
    #: 240. Barrar aqui é melhor que deixar o celular cortar a frase no
    #: meio -- e a tela mostra o contador enquanto se escreve.
    titulo = models.CharField(max_length=65)
    mensagem = models.CharField(max_length=240)
    #: Para onde o toque leva. Vazio abre a loja na página inicial.
    url = models.CharField(
        "Endereço ao tocar",
        max_length=300,
        blank=True,
        help_text="Caminho do site, como /loja/ ou /brinquedo/12/.",
    )
    publico = models.CharField(
        max_length=10, choices=Publico.choices, default=Publico.TODOS,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.RASCUNHO,
        db_index=True,
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="avisos_do_app",
        null=True,
        blank=True,
    )
    enviado_em = models.DateTimeField(null=True, blank=True)
    #: O resultado do disparo, guardado porque a pergunta seguinte é
    #: sempre "chegou em quantos?" -- e sem isto ninguém sabe responder.
    aparelhos_no_envio = models.PositiveIntegerField(default=0)
    entregues = models.PositiveIntegerField(default=0)
    falhas = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Aviso do aplicativo"
        verbose_name_plural = "Avisos do aplicativo"
        ordering = ("-criacao", "-id")

    def __str__(self):
        return f"{self.titulo} ({self.get_status_display()})"

    @property
    def editavel(self):
        return self.status == self.Status.RASCUNHO


class EstadoNotificacao(Prime):
    """Memória do observador para não repetir o mesmo e-mail urgente."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="estados_notificacao",
    )
    chave = models.CharField(max_length=80)
    assinatura = models.CharField(max_length=64, blank=True)
    quantidade = models.PositiveIntegerField(default=0)
    email_enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Estado de notificação"
        verbose_name_plural = "Estados de notificações"
        constraints = [
            models.UniqueConstraint(
                fields=("usuario", "chave"),
                name="notificacao_usuario_chave_unica",
            )
        ]

    def __str__(self):
        return f"{self.usuario} · {self.chave}"


# ======================================================================
# CAMPANHAS DE PROMOÇÕES, COMBOS E CUPONS
# ======================================================================
class CampanhaDivulgacao(Prime):
    """Uma divulgação preparada no painel, com conteúdo congelado.

    A campanha guarda uma cópia do título, texto, imagem e destino. Assim
    o histórico continua inteligível mesmo se a promoção for editada ou
    removida depois. As FKs servem para navegação interna; o cliente recebe
    somente o ``token`` público, nunca o id sequencial do cadastro.
    """

    class Tipo(models.TextChoices):
        PROMOCAO = "promocao", "Promoção"
        COMBO = "combo", "Combo"
        CUPOM = "cupom", "Cupom"

    class Status(models.TextChoices):
        FILA = "fila", "Na fila"
        EM_ANDAMENTO = "andamento", "Em andamento"
        CONCLUIDA = "concluida", "Concluída"
        PARCIAL = "parcial", "Concluída com falhas"
        FALHA = "falha", "Falhou"
        CANCELADA = "cancelada", "Cancelada"

    class Segmento(models.TextChoices):
        TODOS = "todos", "Todos os clientes ativos"
        RESIDENCIAL = "residencial", "Clientes residenciais"
        COMERCIAL = "comercial", "Empresas e comércios"
        BUFFET = "buffet", "Buffets parceiros"
        CONDOMINIO = "condominio", "Condomínios"
        ESCOLA = "escola", "Escolas"
        ORGAO = "orgao", "Órgãos públicos"

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, db_index=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.FILA,
        db_index=True,
    )
    segmento = models.CharField(
        max_length=14,
        choices=Segmento.choices,
        default=Segmento.TODOS,
    )
    promocao = models.ForeignKey(
        "core.Promocoes",
        on_delete=models.SET_NULL,
        related_name="campanhas_divulgacao",
        null=True,
        blank=True,
    )
    combo = models.ForeignKey(
        "core.Combos",
        on_delete=models.SET_NULL,
        related_name="campanhas_divulgacao",
        null=True,
        blank=True,
    )
    cupom = models.ForeignKey(
        "core.Cupom",
        on_delete=models.SET_NULL,
        related_name="campanhas_divulgacao",
        null=True,
        blank=True,
    )
    titulo = models.CharField(max_length=140)
    mensagem = models.TextField(max_length=1200)
    imagem_url = models.URLField(max_length=700, blank=True)
    destino_url = models.URLField(max_length=700, blank=True)
    codigo_cupom = models.CharField(max_length=20, blank=True)
    canal_email = models.BooleanField(default=False)
    canal_whatsapp = models.BooleanField(default=False)
    total_destinatarios = models.PositiveIntegerField(default=0)
    total_enviados = models.PositiveIntegerField(default=0)
    total_falhas = models.PositiveIntegerField(default=0)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="campanhas_divulgacao",
        null=True,
        blank=True,
    )

    @property
    def caminho_publico(self):
        from django.urls import reverse

        return reverse(
            "campanha_publica",
            args=[self.token],
            urlconf=settings.ROOT_URLCONF,
        )

    @property
    def progresso_percentual(self):
        if not self.total_destinatarios:
            return 0
        encerrados = self.total_enviados + self.total_falhas
        return min(100, round(encerrados * 100 / self.total_destinatarios))

    def recalcular(self, salvar=True):
        """Deriva contadores e estado das entregas; nunca soma na mão."""
        entregas = self.entregas.all()
        total = entregas.count()
        enviados = entregas.filter(status=EntregaCampanha.Status.ENVIADO).count()
        falhas = entregas.filter(status=EntregaCampanha.Status.FALHOU).count()
        abertos = entregas.filter(status__in=(
            EntregaCampanha.Status.PENDENTE,
            EntregaCampanha.Status.PROCESSANDO,
            EntregaCampanha.Status.AGUARDANDO_ACAO,
        )).exists()

        if self.status != self.Status.CANCELADA:
            if not total:
                estado = self.Status.FALHA
            elif abertos:
                estado = self.Status.EM_ANDAMENTO
            elif falhas:
                estado = self.Status.PARCIAL if enviados else self.Status.FALHA
            else:
                estado = self.Status.CONCLUIDA
            self.status = estado
        self.total_destinatarios = total
        self.total_enviados = enviados
        self.total_falhas = falhas
        if salvar:
            self.save(update_fields=(
                "status", "total_destinatarios", "total_enviados",
                "total_falhas", "atualizado",
            ))
        return self

    class Meta:
        verbose_name = "Campanha de divulgação"
        verbose_name_plural = "Campanhas de divulgação"
        ordering = ("-criacao", "-id")
        indexes = [
            models.Index(fields=("status", "criacao"), name="campanha_status_data_idx"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.titulo}"


class EntregaCampanha(Prime):
    """Um canal para um destinatário, com endereço congelado e deduplicado."""

    class Canal(models.TextChoices):
        EMAIL = "email", "E-mail"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PROCESSANDO = "processando", "Processando"
        AGUARDANDO_ACAO = "aguardando", "Aguardando envio no WhatsApp"
        ENVIADO = "enviado", "Enviado"
        FALHOU = "falhou", "Falhou"
        IGNORADO = "ignorado", "Ignorado"

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    campanha = models.ForeignKey(
        CampanhaDivulgacao,
        on_delete=models.CASCADE,
        related_name="entregas",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        related_name="entregas_campanha",
        null=True,
        blank=True,
    )
    canal = models.CharField(max_length=10, choices=Canal.choices, db_index=True)
    nome_destinatario = models.CharField(max_length=120)
    destino = models.CharField(max_length=254)
    destino_chave = models.CharField(max_length=64, editable=False)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
    )
    tentativas = models.PositiveSmallIntegerField(default=0)
    proxima_tentativa_em = models.DateTimeField(null=True, blank=True, db_index=True)
    processando_desde = models.DateTimeField(null=True, blank=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    erro = models.CharField(max_length=300, blank=True)

    def save(self, *args, **kwargs):
        if not self.destino_chave:
            import hashlib

            normalizado = (self.destino or "").strip().casefold()
            self.destino_chave = hashlib.sha256(normalizado.encode("utf-8")).hexdigest()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Entrega de campanha"
        verbose_name_plural = "Entregas de campanhas"
        ordering = ("canal", "nome_destinatario", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("campanha", "canal", "destino_chave"),
                name="campanha_canal_destino_unico",
            ),
        ]
        indexes = [
            models.Index(
                fields=("canal", "status", "proxima_tentativa_em"),
                name="entrega_fila_canal_idx",
            ),
        ]

    def __str__(self):
        return f"{self.campanha} · {self.get_canal_display()} · {self.nome_destinatario}"


class ExclusaoRegistrada(models.Model):
    """Quem apagou o quê, quando, e por quê.

    POR QUE ISTO EXISTE. O superusuário passou a poder excluir qualquer
    coisa do sistema -- inclusive proposta enviada, O.S. concluída e
    pedido pago, que as regras normais protegem justamente por serem
    histórico. É a decisão certa: quem responde pela empresa precisa poder
    limpar um registro errado sem depender de ninguém.

    Só que histórico apagado em silêncio é pior do que histórico errado.
    Daqui a seis meses, "onde foi parar a proposta 412?" não pode ser uma
    pergunta sem resposta. Então a exclusão continua liberada, e passa a
    deixar rastro: o que era, quem apagou, quando, e o motivo escrito na
    hora.

    O rastro guarda TEXTO, não chave estrangeira. Uma referência ao objeto
    apagado não sobrevive ao apagamento; o resumo, sim.
    """

    quando = models.DateTimeField(auto_now_add=True, db_index=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="exclusoes_registradas",
        help_text="Fica nulo se a conta for removida depois; o nome abaixo permanece.",
    )
    autor_nome = models.CharField(max_length=150)

    tipo = models.CharField(
        max_length=60,
        db_index=True,
        help_text="Modelo do objeto apagado, em linguagem de gente: Orçamento, O.S.…",
    )
    identificacao = models.CharField(
        max_length=200,
        help_text="Como o objeto era chamado na tela: '#412 — Buffet Alegria'.",
    )
    resumo = models.TextField(
        blank=True,
        help_text="O que ele continha, para o caso de alguém precisar reconstituir.",
    )
    motivo = models.CharField(
        max_length=240,
        blank=True,
        help_text="O que a pessoa escreveu ao confirmar.",
    )
    #: Verdadeiro quando as regras normais teriam recusado a exclusão e
    #: ela só aconteceu porque quem pediu é superusuário. É o que separa
    #: "apagou um rascunho" de "apagou um documento que já foi ao cliente".
    forcada = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = "Exclusão registrada"
        verbose_name_plural = "Exclusões registradas"
        ordering = ("-quando", "-id")

    def __str__(self):
        marca = " (forçada)" if self.forcada else ""
        return f"{self.tipo} {self.identificacao}{marca}"


class EmailIdentidade(models.Model):
    """Reserva transacional de e-mail, mantida pelos gatilhos do banco.

    A reserva é POR ESCOPO, e essa é a regra inteira.

    Cliente e conta de acesso são cadastros diferentes, com vidas
    diferentes: o dono do buffet tem login para acompanhar as propostas
    E é o cliente que recebe o orçamento. Exigir endereços distintos nos
    dois obrigava a inventar um e-mail para a mesma pessoa -- e não
    protegia nada, porque nenhum caminho do sistema junta cliente e
    usuário pelo e-mail.

    O que a reserva impede continua sendo o que sempre foi problema:
    dois CLIENTES com o mesmo contato (duplicidade de cadastro) e duas
    CONTAS com o mesmo endereço (recuperação de senha ambígua).
    """

    #: `usuario` cobre auth_user e os aliases do allauth -- são a mesma
    #: conta. `cliente` cobre o cadastro comercial.
    class Escopo(models.TextChoices):
        USUARIO = "usuario", "Conta de acesso"
        CLIENTE = "cliente", "Cliente"

    escopo = models.CharField(max_length=8, choices=Escopo.choices)
    email = models.CharField(max_length=254)
    titular = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("escopo", "email"),
                name="email_unico_por_escopo",
            ),
        ]

    def __str__(self):
        return f"{self.email} ({self.get_escopo_display()})"
