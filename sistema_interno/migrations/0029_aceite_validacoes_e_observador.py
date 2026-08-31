"""Aceite eletrônico, validação de documento e observador de notificação.

Só esquema. O preenchimento das colunas novas mora na 0032: dados e
esquema no mesmo arquivo estouram no Postgres com 'pending trigger
events', e o SQLite dos testes não reproduz.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sistema_interno", "0028_alter_ordemservico_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="canal_telefone",
            field=models.CharField(
                choices=[
                    ("whatsapp", "WhatsApp confirmado"),
                    ("telefone", "Telefone, sem WhatsApp"),
                    ("nao_confirmado", "Ainda não confirmado"),
                ],
                default="nao_confirmado",
                help_text="Evita tratar um telefone comum como WhatsApp sem confirmação.",
                max_length=16,
                verbose_name="Uso do número",
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="documento_chave",
            field=models.CharField(
                blank=True,
                db_index=True,
                editable=False,
                help_text="CPF/CNPJ normalizado, usado apenas para evitar duplicidades.",
                max_length=14,
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="documento_valido",
            field=models.BooleanField(
                db_index=True,
                default=False,
                editable=False,
                help_text="Confere formato e dígitos verificadores; não consulta a Receita.",
            ),
        ),
        migrations.CreateModel(
            name="AceiteOrcamento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo_publico", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("assinante_nome", models.CharField(max_length=120)),
                ("assinante_documento", models.CharField(max_length=14)),
                ("consentimento", models.BooleanField(default=True)),
                ("proposta_hash", models.CharField(max_length=64)),
                ("ip_hash", models.CharField(max_length=64)),
                ("navegador_hash", models.CharField(max_length=64)),
                ("termos_versao", models.CharField(default="2026-08", max_length=20)),
                ("assinado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "orcamento",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="aceite_eletronico",
                        to="sistema_interno.orcamento",
                    ),
                ),
            ],
            options={
                "verbose_name": "Aceite eletrônico de orçamento",
                "verbose_name_plural": "Aceites eletrônicos de orçamentos",
                "ordering": ("-assinado_em",),
            },
        ),
        migrations.CreateModel(
            name="EstadoNotificacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criacao", models.DateTimeField(auto_now_add=True, null=True)),
                ("atualizado", models.DateTimeField(auto_now=True, null=True)),
                ("chave", models.CharField(max_length=80)),
                ("assinatura", models.CharField(blank=True, max_length=64)),
                ("quantidade", models.PositiveIntegerField(default=0)),
                ("email_enviado_em", models.DateTimeField(blank=True, null=True)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="estados_notificacao",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Estado de notificação",
                "verbose_name_plural": "Estados de notificações",
            },
        ),
        migrations.AddConstraint(
            model_name="estadonotificacao",
            constraint=models.UniqueConstraint(
                fields=("usuario", "chave"),
                name="notificacao_usuario_chave_unica",
            ),
        ),
    ]
