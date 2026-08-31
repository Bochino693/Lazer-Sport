import re
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _digito(valores, pesos):
    resto = sum(valor * peso for valor, peso in zip(valores, pesos)) % 11
    return 0 if resto < 2 else 11 - resto


def _documento_valido(valor):
    chave = re.sub(r"[^0-9A-Z]", "", (valor or "").upper())[:14]
    if len(chave) == 11 and chave.isdigit():
        if len(set(chave)) == 1:
            return False
        base = [int(c) for c in chave[:9]]
        d1 = _digito(base, range(10, 1, -1))
        d2 = _digito(base + [d1], range(11, 1, -1))
        return chave[-2:] == f"{d1}{d2}"
    if len(chave) != 14 or not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", chave):
        return False
    base = [ord(c) - 48 for c in chave[:12]]
    d1 = _digito(base, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    d2 = _digito(base + [d1], (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return chave[-2:] == f"{d1}{d2}"


def preencher_clientes(apps, schema_editor):
    Cliente = apps.get_model("sistema_interno", "Cliente")
    lote = []
    for cliente in Cliente.objects.all().iterator(chunk_size=500):
        cliente.documento_chave = re.sub(
            r"[^0-9A-Z]", "", (cliente.documento or "").upper()
        )[:14]
        cliente.documento_valido = _documento_valido(cliente.documento)
        if cliente.telefone:
            # Compatibilidade: antes todo campo era rotulado WhatsApp e as
            # propostas existentes dependem dessa interpretação.
            cliente.canal_telefone = "whatsapp"
        lote.append(cliente)
        if len(lote) == 500:
            Cliente.objects.bulk_update(
                lote, ("documento_chave", "documento_valido", "canal_telefone")
            )
            lote = []
    if lote:
        Cliente.objects.bulk_update(
            lote, ("documento_chave", "documento_valido", "canal_telefone")
        )


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
        migrations.RunPython(preencher_clientes, migrations.RunPython.noop),
    ]
