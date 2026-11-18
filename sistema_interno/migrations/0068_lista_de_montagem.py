# A LISTA DE MONTAGEM (LEIA-ME-V10, seção 108) -- SÓ ESQUEMA.
#
# As regras da produção (uma linha, que o painel muda), a produção de cada
# origem (um pedido do site OU um orçamento: a chegada que ordena a fila,
# o pronto, o entregue, as etapas que o cliente acompanha e os avisos já
# mandados) e as unidades a montar (uma por máquina: a trilha, a etapa, as
# datas previstas, a posição na fila). Os dados (a linha das regras) vêm
# na 0069.

import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0111_pecasreposicao_uso"),
        ("sistema_interno", "0067_orcamento_codigo_unico"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracaoProducao",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("criacao", models.DateTimeField(auto_now_add=True, null=True)),
                ("atualizado", models.DateTimeField(auto_now=True, null=True)),
                (
                    "limite_m3",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("2.50"),
                        max_digits=6,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0.10")),
                            django.core.validators.MaxValueValidator(Decimal("99")),
                        ],
                        verbose_name="Até quantos m³ a máquina é de montagem curta",
                    ),
                ),
                (
                    "dias_ate_limite",
                    models.PositiveSmallIntegerField(
                        default=4,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(60),
                        ],
                        verbose_name="Dias úteis até o limite",
                    ),
                ),
                (
                    "dias_acima_limite",
                    models.PositiveSmallIntegerField(
                        default=5,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(60),
                        ],
                        verbose_name="Dias úteis acima do limite (e sem medida)",
                    ),
                ),
                (
                    "dias_pecas",
                    models.PositiveSmallIntegerField(
                        default=3,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(60),
                        ],
                        verbose_name="Dias úteis das peças de reposição e dos kits",
                    ),
                ),
                (
                    "dias_projeto",
                    models.PositiveSmallIntegerField(
                        default=30,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(250),
                        ],
                        verbose_name="Dias úteis de cada brinquedão / espaço",
                    ),
                ),
                (
                    "capacidade_maquinas",
                    models.PositiveSmallIntegerField(
                        default=3,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(50),
                        ],
                        verbose_name="Máquinas em montagem ao mesmo tempo",
                    ),
                ),
                (
                    "capacidade_projetos",
                    models.PositiveSmallIntegerField(
                        default=1,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(20),
                        ],
                        verbose_name="Brinquedões em montagem ao mesmo tempo",
                    ),
                ),
                (
                    "fila_min_dias",
                    models.PositiveSmallIntegerField(
                        default=15,
                        validators=[django.core.validators.MaxValueValidator(250)],
                        verbose_name="Fila das máquinas: mínimo (dias úteis)",
                    ),
                ),
                (
                    "fila_max_dias",
                    models.PositiveSmallIntegerField(
                        default=30,
                        validators=[django.core.validators.MaxValueValidator(250)],
                        verbose_name="Fila das máquinas: máximo (dias úteis)",
                    ),
                ),
                (
                    "palavras_projeto",
                    models.TextField(
                        blank=True,
                        default="brinquedão, brinquedões, trampolim, trampolins, cama elástica, escalada, ninja, espaço esportivo, quadra, playground, parque, casinha, cenográfica",
                        help_text="Separadas por vírgula; valem no nome do brinquedo e da categoria.",
                        verbose_name="Palavras de brinquedão / espaço",
                    ),
                ),
                (
                    "categorias_projeto",
                    models.ManyToManyField(
                        blank=True,
                        related_name="+",
                        to="core.categoriasbrinquedos",
                        verbose_name="Categorias de brinquedão / espaço",
                    ),
                ),
            ],
            options={
                "verbose_name": "Regras da produção",
                "verbose_name_plural": "Regras da produção",
            },
        ),
        migrations.CreateModel(
            name="ProducaoOrigem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("criacao", models.DateTimeField(auto_now_add=True, null=True)),
                ("atualizado", models.DateTimeField(auto_now=True, null=True)),
                (
                    "chegada",
                    models.DateTimeField(
                        db_index=True, verbose_name="Entrou na produção em"
                    ),
                ),
                (
                    "situacao",
                    models.CharField(
                        choices=[
                            ("fila", "Na fila"),
                            ("producao", "Em produção"),
                            ("pronta", "Pronta"),
                            ("entregue", "Entregue"),
                            ("cancelada", "Cancelada"),
                        ],
                        db_index=True,
                        default="fila",
                        max_length=10,
                    ),
                ),
                ("pronto_em", models.DateTimeField(blank=True, null=True)),
                ("entregue_em", models.DateTimeField(blank=True, null=True)),
                ("cancelada_em", models.DateTimeField(blank=True, null=True)),
                ("etapas_em", models.JSONField(blank=True, default=dict)),
                ("avisos", models.JSONField(blank=True, default=dict)),
                ("prazo_automatico", models.BooleanField(default=False)),
                ("avancou_origem", models.BooleanField(default=False)),
                (
                    "orcamento",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="producao",
                        to="sistema_interno.orcamento",
                    ),
                ),
                (
                    "pedido",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="producao",
                        to="core.pedido",
                    ),
                ),
            ],
            options={
                "verbose_name": "Produção de um pedido ou orçamento",
                "verbose_name_plural": "Produção dos pedidos e orçamentos",
                "ordering": ("chegada", "id"),
            },
        ),
        migrations.CreateModel(
            name="UnidadeMontagem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("criacao", models.DateTimeField(auto_now_add=True, null=True)),
                ("atualizado", models.DateTimeField(auto_now=True, null=True)),
                ("numero", models.PositiveSmallIntegerField(default=1)),
                ("de", models.PositiveSmallIntegerField(default=1)),
                ("nome", models.CharField(max_length=200)),
                (
                    "variante",
                    models.CharField(
                        blank=True, max_length=80, verbose_name="Adesivo / variante"
                    ),
                ),
                (
                    "trilha",
                    models.CharField(
                        choices=[
                            ("maquina", "Máquina"),
                            ("projeto", "Brinquedão / espaço"),
                            ("peca", "Peça de reposição"),
                            ("kit", "Kit eletrônico"),
                        ],
                        db_index=True,
                        default="maquina",
                        max_length=10,
                    ),
                ),
                (
                    "situacao",
                    models.CharField(
                        choices=[
                            ("fila", "Na fila"),
                            ("producao", "Em produção"),
                            ("pronta", "Pronta"),
                            ("entregue", "Entregue"),
                            ("cancelada", "Cancelada"),
                        ],
                        db_index=True,
                        default="fila",
                        max_length=10,
                    ),
                ),
                ("etapa", models.CharField(blank=True, max_length=20)),
                ("etapas_em", models.JSONField(blank=True, default=dict)),
                ("previstas", models.JSONField(blank=True, default=dict)),
                (
                    "dias",
                    models.PositiveSmallIntegerField(
                        blank=True, null=True, verbose_name="Dias úteis de montagem"
                    ),
                ),
                ("posicao", models.PositiveIntegerField(blank=True, null=True)),
                ("chegada", models.DateTimeField(db_index=True)),
                (
                    "entrou_em",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Entrou em montagem em"
                    ),
                ),
                ("previsao_de", models.DateField(blank=True, null=True)),
                ("previsao_ate", models.DateField(blank=True, null=True)),
                (
                    "atualizado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "brinquedo",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="core.brinquedos",
                    ),
                ),
                (
                    "item_orcamento",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="sistema_interno.itemorcamento",
                    ),
                ),
                (
                    "item_pedido",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="core.itempedido",
                    ),
                ),
                (
                    "peca",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="core.pecasreposicao",
                    ),
                ),
                (
                    "producao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="unidades",
                        to="sistema_interno.producaoorigem",
                    ),
                ),
            ],
            options={
                "verbose_name": "Unidade a montar",
                "verbose_name_plural": "Lista de montagem",
                "ordering": ("chegada", "producao_id", "id"),
            },
        ),
        migrations.AddConstraint(
            model_name="producaoorigem",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("orcamento__isnull", True), ("pedido__isnull", False)),
                    models.Q(("orcamento__isnull", False), ("pedido__isnull", True)),
                    _connector="OR",
                ),
                name="producao_de_uma_origem_so",
            ),
        ),
        migrations.AddIndex(
            model_name="unidademontagem",
            index=models.Index(
                fields=["trilha", "situacao"], name="montagem_trilha_situacao_idx"
            ),
        ),
    ]
