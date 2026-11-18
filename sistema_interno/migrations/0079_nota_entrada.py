"""Entrada de nota fiscal no estoque (LEIA-ME-V10, seção 115).

Só esquema: NotaEntrada, ItemNotaEntrada e o elo da movimentação de
estoque com a nota. A unicidade da nota lançada (chave de acesso, ou CNPJ +
número + série) vale no banco, como índice parcial, só entre as LANÇADAS:
uma leitura em conferência pode repetir a nota sem travar ninguém.
"""

import django.db.models.deletion
import django.utils.timezone
import sistema_interno.notas_entrada.armazenamento
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0078_apagar_pedidos_de_teste"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotaEntrada",
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
                    "situacao",
                    models.CharField(
                        choices=[
                            ("conferencia", "Em conferência"),
                            ("lancada", "Lançada no estoque"),
                        ],
                        db_index=True,
                        default="conferencia",
                        max_length=12,
                    ),
                ),
                (
                    "formato",
                    models.CharField(
                        choices=[("pdf", "PDF (DANFE)"), ("xml", "XML da NF-e")],
                        max_length=4,
                    ),
                ),
                (
                    "arquivo",
                    models.FileField(
                        blank=True,
                        storage=sistema_interno.notas_entrada.armazenamento.ArmazenamentoDasNotas(),
                        upload_to=sistema_interno.notas_entrada.armazenamento.caminho_da_nota,
                    ),
                ),
                ("nome_arquivo", models.CharField(blank=True, max_length=150)),
                ("tamanho_arquivo", models.PositiveIntegerField(default=0)),
                ("sha256", models.CharField(blank=True, db_index=True, max_length=64)),
                (
                    "fornecedor_nome",
                    models.CharField(
                        blank=True,
                        max_length=120,
                        verbose_name="fornecedor (como na nota)",
                    ),
                ),
                (
                    "fornecedor_cnpj",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        max_length=14,
                        verbose_name="CNPJ / CPF do emitente",
                    ),
                ),
                (
                    "numero",
                    models.CharField(blank=True, max_length=9, verbose_name="número"),
                ),
                (
                    "serie",
                    models.CharField(blank=True, max_length=3, verbose_name="série"),
                ),
                (
                    "emissao",
                    models.DateField(blank=True, null=True, verbose_name="emissão"),
                ),
                (
                    "chave_acesso",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        max_length=44,
                        verbose_name="chave de acesso",
                    ),
                ),
                (
                    "valor_produtos",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=14,
                        verbose_name="total dos produtos",
                    ),
                ),
                (
                    "valor_total",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=14,
                        verbose_name="total da nota",
                    ),
                ),
                (
                    "data_entrada",
                    models.DateField(
                        default=django.utils.timezone.localdate,
                        verbose_name="data de entrada",
                    ),
                ),
                ("avisos", models.JSONField(blank=True, default=list)),
                ("observacoes", models.TextField(blank=True)),
                ("lancada_em", models.DateTimeField(blank=True, null=True)),
                (
                    "compra",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="nota_entrada",
                        to="sistema_interno.comprasmensais",
                    ),
                ),
                (
                    "enviada_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "fornecedor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notas_entrada",
                        to="sistema_interno.fornecedor",
                    ),
                ),
                (
                    "lancada_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notas_entrada_lancadas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Nota fiscal de entrada",
                "verbose_name_plural": "Notas fiscais de entrada",
                "ordering": ("-criacao", "-id"),
            },
        ),
        migrations.CreateModel(
            name="ItemNotaEntrada",
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
                ("ordem", models.PositiveIntegerField(default=0)),
                ("linhas_nota", models.CharField(blank=True, max_length=200)),
                (
                    "codigo",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        max_length=60,
                        verbose_name="código do fornecedor",
                    ),
                ),
                ("descricao", models.CharField(max_length=250)),
                ("complemento", models.CharField(blank=True, max_length=250)),
                ("ncm", models.CharField(blank=True, max_length=8, verbose_name="NCM")),
                ("unidade_nota", models.CharField(blank=True, max_length=6)),
                (
                    "quantidade_nota",
                    models.DecimalField(
                        decimal_places=4, default=Decimal("0"), max_digits=15
                    ),
                ),
                (
                    "valor_unitario_nota",
                    models.DecimalField(
                        decimal_places=4, default=Decimal("0"), max_digits=16
                    ),
                ),
                (
                    "valor_total",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0.00"), max_digits=14
                    ),
                ),
                (
                    "ligacao",
                    models.CharField(
                        choices=[
                            ("codigo", "Pelo código do fornecedor"),
                            ("nome", "Pelo nome"),
                            ("parecido", "Nome parecido"),
                            ("manual", "Escolhido na conferência"),
                            ("novo", "Material novo"),
                            ("fora", "Não entra no estoque"),
                        ],
                        default="novo",
                        max_length=10,
                    ),
                ),
                ("semelhanca", models.PositiveSmallIntegerField(default=0)),
                (
                    "nome_material",
                    models.CharField(
                        blank=True, max_length=90, verbose_name="nome do material novo"
                    ),
                ),
                (
                    "unidade",
                    models.CharField(
                        choices=[
                            ("un", "Unidade"),
                            ("pc", "Peça"),
                            ("m", "Metro"),
                            ("m2", "Metro quadrado"),
                            ("kg", "Quilo"),
                            ("l", "Litro"),
                            ("cx", "Caixa"),
                            ("rl", "Rolo"),
                            ("par", "Par"),
                        ],
                        default="un",
                        max_length=5,
                    ),
                ),
                (
                    "quantidade",
                    models.PositiveIntegerField(
                        default=0, verbose_name="quantidade no estoque"
                    ),
                ),
                (
                    "local",
                    models.CharField(
                        blank=True, max_length=90, verbose_name="local de guarda"
                    ),
                ),
                ("aviso", models.CharField(blank=True, max_length=200)),
                (
                    "material",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="itens_nota_entrada",
                        to="sistema_interno.material",
                    ),
                ),
                (
                    "movimento",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="itens_nota",
                        to="sistema_interno.movimentoestoque",
                    ),
                ),
                (
                    "nota",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="itens",
                        to="sistema_interno.notaentrada",
                    ),
                ),
            ],
            options={
                "verbose_name": "Item da nota de entrada",
                "verbose_name_plural": "Itens das notas de entrada",
                "ordering": ("nota", "ordem", "id"),
            },
        ),
        migrations.AddField(
            model_name="movimentoestoque",
            name="nota_entrada",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="movimentos",
                to="sistema_interno.notaentrada",
            ),
        ),
        migrations.AddConstraint(
            model_name="notaentrada",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("situacao", "lancada"),
                    models.Q(("chave_acesso", ""), _negated=True),
                ),
                fields=("chave_acesso",),
                name="nota_entrada_chave_unica",
            ),
        ),
        migrations.AddConstraint(
            model_name="notaentrada",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("situacao", "lancada"),
                    models.Q(("fornecedor_cnpj", ""), _negated=True),
                    models.Q(("numero", ""), _negated=True),
                ),
                fields=("fornecedor_cnpj", "numero", "serie"),
                name="nota_entrada_numero_unico",
            ),
        ),
    ]
