# OS DADOS DO VENDEDOR NO CONTRATO (LEIA-ME-V10, seção 107).
#
# SÓ ESQUEMA: a tabela de uma linha que a tela "Dados do contrato" edita.
# A linha nasce na 0069 (só dados), com os dados PÚBLICOS da empresa; os
# do representante (nome, RG, endereço residencial) ficam vazios -- não
# moram em migração: o dono preenche no painel.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0067_orcamento_codigo_unico"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DadosContrato",
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
                    "nome_fantasia",
                    models.CharField(
                        default="Brinquedos Lazer & Sport",
                        max_length=120,
                        verbose_name="Nome fantasia",
                    ),
                ),
                (
                    "razao_social",
                    models.CharField(
                        default="Fábrica de Brinquedos Lazer & Sport Oficial – LTDA",
                        max_length=160,
                        verbose_name="Razão social",
                    ),
                ),
                (
                    "cnpj",
                    models.CharField(
                        default="54.486.908/0001-86", max_length=18, verbose_name="CNPJ"
                    ),
                ),
                (
                    "endereco_sede",
                    models.CharField(
                        default="Rua São Roque de Minas, n. 104, Jardim Peri, São Paulo, Capital",
                        help_text="Como sai no contrato: “com sede na …”.",
                        max_length=240,
                        verbose_name="Endereço da sede",
                    ),
                ),
                (
                    "cidade",
                    models.CharField(
                        default="São Paulo",
                        help_text="A cidade do fecho: “São Paulo, 18 de novembro de 2026”.",
                        max_length=80,
                        verbose_name="Cidade do contrato",
                    ),
                ),
                (
                    "representante_nome",
                    models.CharField(
                        blank=True,
                        help_text="Quem assina pela empresa (o proprietário).",
                        max_length=160,
                        verbose_name="Nome do representante",
                    ),
                ),
                (
                    "representante_rg",
                    models.CharField(
                        blank=True, max_length=30, verbose_name="RG do representante"
                    ),
                ),
                (
                    "representante_endereco",
                    models.CharField(
                        blank=True,
                        help_text="Como sai no contrato: “residente e domiciliado na …”.",
                        max_length=240,
                        verbose_name="Endereço residencial do representante",
                    ),
                ),
                (
                    "atualizado_por",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Dados do contrato",
                "verbose_name_plural": "Dados do contrato",
            },
        ),
    ]
