from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from core.models import Brinquedos, Pedido, Venda, ItemPedido


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
    nome_cliente = models.CharField(max_length=90)
    telefone = models.CharField(max_length=14)
    email = models.CharField(max_length=150, null=True)

    def __str__(self):
        return self.nome_cliente

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"


class EnderecoCliente(Prime):
    cep = models.CharField(max_length=18)
    endereco = models.CharField(max_length=120)
    numero = models.CharField(max_length=5)
    bairro = models.CharField(max_length=50)
    cidade = models.CharField(max_length=25)
    estado = models.CharField(max_length=20)
    cliente = models.ForeignKey(Cliente, related_name='enderecos', on_delete=models.CASCADE, null=True)

    latitude = models.DecimalField(
        max_digits=50, decimal_places=30, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=50, decimal_places=30, null=True, blank=True
    )

    def __str__(self):
        return self.endereco

    class Meta:
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


class TipoMaterial(Prime):
    descricao = models.CharField(max_length=120)

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
        help_text="Código usado na prateleira, na nota ou no catálogo do fornecedor.",
    )
    unidade = models.CharField(
        max_length=5,
        choices=Unidade.choices,
        default=Unidade.UNIDADE,
    )
    tipo_material = models.ForeignKey(TipoMaterial, on_delete=models.SET_NULL, related_name='material', null=True, blank=True)
    brinquedos_associados = models.ManyToManyField(Brinquedos, related_name='materiais', blank=True)
    ativo = models.BooleanField(default=True)

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


class Montadores(Prime):
    nome_montador = models.CharField(max_length=90)

    def __str__(self):
        return self.nome_montador

    class Meta:
        verbose_name = "Montadores"
        verbose_name_plural = "Montadores"


class Setores(Prime):
    nome_setor = models.CharField(max_length=120)

    def __str__(self):
        return self.nome_setor

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "Setores"


class EstoqueMaterial(Prime):
    """Um material guardado num local. É aqui que fica o valor pago."""

    ESTAVEL = "estavel"
    ATENCAO = "atencao"
    CRITICO = "critico"

    descricao_local = models.CharField("Local de guarda", max_length=90)
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='estoque')
    quantidade = models.IntegerField(default=1)
    # max_digits=6 travava o cadastro em R$ 9.999,99, o que não cobre
    # lona, motor, inflável nem compra fechada de fornecedor.
    preco_fornecedor = models.DecimalField(
        "Valor pago por unidade",
        decimal_places=2,
        max_digits=12,
    )
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
        on_delete=models.CASCADE,
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

    @property
    def valor_total(self):
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
        quantidade = int(quantidade)
        if quantidade <= 0:
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

        travado.quantidade = resultante

        campos = ["quantidade", "atualizado"]
        valor_unitario = extras.get("valor_unitario")
        if tipo == cls.Tipo.ENTRADA and valor_unitario:
            # A compra mais recente passa a ser o valor de referência.
            travado.preco_fornecedor = valor_unitario
            campos.append("preco_fornecedor")

        travado.save(update_fields=campos)

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
        choices=(('site', 'Site'), ('interno', 'Interno')),
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
        """Último preço pago; na falta dele, zero em vez de quebrar a tela."""
        local = (
            self.material.estoque
            .exclude(preco_fornecedor=None)
            .order_by("-atualizado")
            .first()
        )
        return local.preco_fornecedor if local else Decimal("0.00")

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
    montador = models.ForeignKey(
        Montadores,
        on_delete=models.SET_NULL,
        related_name="ordens",
        null=True,
        blank=True,
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
    colaborador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="producoes_atribuidas",
        null=True,
        blank=True,
        help_text="Funcionário que executará e atualizará as etapas.",
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
class Orcamento(Prime):
    """Proposta comercial montada no painel interno."""

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        ENVIADO = "enviado", "Enviado"
        APROVADO = "aprovado", "Aprovado"
        RECUSADO = "recusado", "Recusado"
        EXPIRADO = "expirado", "Expirado"

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

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.RASCUNHO,
        db_index=True,
    )
    validade = models.DateField(null=True, blank=True)
    desconto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    frete = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    observacoes = models.TextField(blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="orcamentos",
        null=True,
        blank=True,
    )

    @property
    def destinatario(self):
        if self.cliente:
            return self.cliente.nome_cliente
        return self.nome_cliente or "Sem cliente"

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

    @property
    def vencido(self):
        return bool(
            self.validade
            and self.validade < timezone.localdate()
            and self.status in (self.Status.RASCUNHO, self.Status.ENVIADO)
        )

    def __str__(self):
        return f"Orçamento #{self.pk} — {self.destinatario}"

    class Meta:
        verbose_name = "Orçamento"
        verbose_name_plural = "Orçamentos"
        ordering = ("-criacao", "-id")


class ItemOrcamento(Prime):
    orcamento = models.ForeignKey(
        Orcamento,
        on_delete=models.CASCADE,
        related_name="itens",
    )
    # A descrição é gravada mesmo quando há produto associado: se o cadastro
    # mudar de nome depois, a proposta enviada ao cliente continua valendo.
    descricao = models.CharField(max_length=180)
    produto = models.ForeignKey(
        ProdutoInterno,
        on_delete=models.SET_NULL,
        related_name="itens_orcamento",
        null=True,
        blank=True,
    )
    quantidade = models.PositiveIntegerField(default=1)
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    @property
    def subtotal(self):
        return (self.valor_unitario * self.quantidade).quantize(Decimal("0.01"))

    def __str__(self):
        return self.descricao

    class Meta:
        verbose_name = "Item do orçamento"
        verbose_name_plural = "Itens do orçamento"
        ordering = ("id",)
