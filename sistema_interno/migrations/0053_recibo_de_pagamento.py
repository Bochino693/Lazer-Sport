"""O recibo de pagamento ganha tabela própria.

O dinheiro já era registrado no orçamento (`valor_pago`); o que não
existia era o DOCUMENTO. Ele não é uma consulta ao orçamento: guarda os
valores do momento em que foi emitido, porque um recibo entregue não
pode mudar de quantia depois -- ver `sistema_interno/recibos.py`.
"""

import django.db.models.deletion
import sistema_interno.models
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0052_saldos_iniciais_custos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReciboOrcamento",
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
                (
                    "codigo_publico",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                (
                    "token",
                    models.CharField(
                        db_index=True,
                        default=sistema_interno.models.gerar_token_orcamento,
                        editable=False,
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("sequencia", models.PositiveIntegerField(default=1)),
                ("valor", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "valor_acumulado",
                    models.DecimalField(decimal_places=2, max_digits=12),
                ),
                (
                    "total_documento",
                    models.DecimalField(decimal_places=2, max_digits=12),
                ),
                ("quitacao", models.BooleanField(default=False)),
                ("pagador_nome", models.CharField(max_length=120)),
                ("pagador_documento", models.CharField(blank=True, max_length=20)),
                ("referencia", models.CharField(blank=True, max_length=240)),
                ("forma_pagamento", models.CharField(blank=True, max_length=120)),
                ("observacao", models.CharField(blank=True, max_length=240)),
                ("conteudo_hash", models.CharField(max_length=64)),
                ("emitido_por_nome", models.CharField(max_length=150)),
                ("emitido_em", models.DateTimeField(auto_now_add=True)),
                (
                    "emitido_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recibos_emitidos",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "orcamento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="recibos",
                        to="sistema_interno.orcamento",
                    ),
                ),
            ],
            options={
                "verbose_name": "Recibo de pagamento",
                "verbose_name_plural": "Recibos de pagamento",
                "ordering": ("-emitido_em", "-id"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("orcamento", "sequencia"),
                        name="recibo_sequencia_por_orcamento",
                    )
                ],
            },
        ),
    ]
