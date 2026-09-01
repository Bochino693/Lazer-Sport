from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        (
            "sistema_interno",
            "0036_itemordemservico_peca_ordemservico_motivo_refacao_and_more",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AtividadeOrcamento",
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
                ("orcamento_numero", models.PositiveIntegerField(db_index=True)),
                ("cliente", models.CharField(blank=True, max_length=120)),
                ("autor_nome", models.CharField(max_length=150)),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("criado", "criou"),
                            ("alterado", "alterou"),
                            ("situacao", "mudou a situação de"),
                            ("refeito", "criou uma nova versão de"),
                            ("pagamento", "atualizou o pagamento de"),
                            ("avaliacao", "avaliou"),
                            ("enviado", "preparou o envio de"),
                        ],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                ("resumo", models.CharField(blank=True, max_length=240)),
                (
                    "autor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="atividades_orcamento",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "orcamento",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="atividades",
                        to="sistema_interno.orcamento",
                    ),
                ),
            ],
            options={
                "verbose_name": "Atividade de orçamento",
                "verbose_name_plural": "Atividades de orçamentos",
                "ordering": ("-criacao", "-id"),
                "indexes": [
                    models.Index(
                        fields=["orcamento", "-id"],
                        name="atividade_orcamento_idx",
                    )
                ],
            },
        ),
    ]
