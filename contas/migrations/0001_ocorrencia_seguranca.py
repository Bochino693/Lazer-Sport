"""O registro de segurança das contas (só esquema).

Primeiro passo de três: 0001 cria a tabela das ocorrências, 0002 resolve
os e-mails repetidos que já existem (só dados) e 0003 põe o índice único
no banco (só o índice). Separadas porque dado e esquema na mesma migração
estouram no PostgreSQL ("pending trigger events", ver
sistema_interno/tests_migracoes.py).
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OcorrenciaSeguranca",
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
                    "tipo",
                    models.CharField(
                        choices=[
                            ("email_repetido", "E-mail repetido"),
                            ("login_bloqueado", "Login bloqueado"),
                            ("social_recusado", "Login social recusado"),
                        ],
                        db_index=True,
                        max_length=20,
                        verbose_name="Tipo",
                    ),
                ),
                (
                    "situacao",
                    models.CharField(
                        choices=[
                            ("pendente", "Esperando revisão"),
                            ("reativada", "Conta reativada"),
                            ("mantida", "Mantida bloqueada"),
                            ("liberada", "Login liberado"),
                            ("ciente", "Revisada"),
                        ],
                        db_index=True,
                        default="pendente",
                        max_length=12,
                        verbose_name="Situação",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="Usuário (na hora)"
                    ),
                ),
                (
                    "email_original",
                    models.CharField(
                        blank=True,
                        max_length=254,
                        verbose_name="E-mail que a conta tinha",
                    ),
                ),
                (
                    "login_tentado",
                    models.CharField(
                        blank=True, max_length=254, verbose_name="Login digitado"
                    ),
                ),
                (
                    "ip",
                    models.GenericIPAddressField(
                        blank=True, null=True, verbose_name="IP"
                    ),
                ),
                (
                    "origem",
                    models.CharField(
                        blank=True, max_length=20, verbose_name="Por onde"
                    ),
                ),
                ("motivo", models.TextField(blank=True, verbose_name="Motivo")),
                (
                    "criado_em",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        verbose_name="Quando",
                    ),
                ),
                (
                    "resolvido_em",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Resolvida em"
                    ),
                ),
                (
                    "conta_mantida",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Conta que ficou com o e-mail",
                    ),
                ),
                (
                    "resolvido_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Resolvida por",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ocorrencias_de_seguranca",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Conta",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ocorrência de segurança",
                "verbose_name_plural": "Ocorrências de segurança",
                "ordering": ("-criado_em", "-id"),
            },
        ),
    ]
