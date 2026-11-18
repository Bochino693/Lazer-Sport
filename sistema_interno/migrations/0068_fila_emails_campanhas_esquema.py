# O envio robusto dos e-mails de campanha (LEIA-ME-V10, seção 107).
#
# SÓ ESQUEMA: o estado da fila (pausa do provedor, teto diário, a hora da
# última rodada, o último erro), os descadastros e o contador dos e-mails
# que não saíram de propósito. Os dados (a fila antiga parada pelo defeito)
# ficam na 0069, em arquivo próprio -- ver tests_migracoes.py.
#
# Gerada pelo Django 5.2.8 em 2026-11-18.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0067_orcamento_codigo_unico"),
    ]

    operations = [
        migrations.CreateModel(
            name="EstadoFilaEmails",
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
                    "chave",
                    models.CharField(default="campanhas", max_length=20, unique=True),
                ),
                ("pausada_ate", models.DateTimeField(blank=True, null=True)),
                ("motivo_pausa", models.CharField(blank=True, max_length=300)),
                ("falhas_seguidas", models.PositiveSmallIntegerField(default=0)),
                ("dia", models.DateField(blank=True, null=True)),
                ("enviados_no_dia", models.PositiveIntegerField(default=0)),
                ("ultimo_envio_em", models.DateTimeField(blank=True, null=True)),
                ("ultima_rodada_em", models.DateTimeField(blank=True, null=True)),
                ("ultimo_erro", models.CharField(blank=True, max_length=300)),
                ("ultimo_erro_em", models.DateTimeField(blank=True, null=True)),
                ("atualizado", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Estado da fila de e-mails",
                "verbose_name_plural": "Estado da fila de e-mails",
            },
        ),
        migrations.AddField(
            model_name="campanhadivulgacao",
            name="total_ignorados",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="DescadastroEmail",
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
                ("email", models.EmailField(max_length=254)),
                (
                    "email_chave",
                    models.CharField(editable=False, max_length=64, unique=True),
                ),
                (
                    "origem",
                    models.CharField(
                        choices=[
                            ("link", "Link no rodapé do e-mail"),
                            ("um_clique", "Botão do provedor de e-mail"),
                            ("equipe", "Equipe"),
                        ],
                        default="link",
                        max_length=12,
                    ),
                ),
                (
                    "entrega",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="descadastros",
                        to="sistema_interno.entregacampanha",
                    ),
                ),
            ],
            options={
                "verbose_name": "Descadastro de divulgação",
                "verbose_name_plural": "Descadastros de divulgação",
                "ordering": ("-criacao", "-id"),
            },
        ),
    ]
