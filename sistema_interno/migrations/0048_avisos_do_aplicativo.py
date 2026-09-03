"""A loja passa a poder falar com o celular de quem baixou o aplicativo.

Duas tabelas, e a separação entre elas é a decisão que importa:
`AparelhoDoCliente` é o telefone de um CLIENTE, e nunca se mistura com
`InscricaoPush`, que é o da EQUIPE. Ver `sistema_interno/avisos_app.py`.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sistema_interno", "0047_email_por_escopo"),
    ]

    operations = [
        migrations.CreateModel(
            name="AparelhoDoCliente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criacao", models.DateTimeField(auto_now_add=True, null=True)),
                ("atualizado", models.DateTimeField(auto_now=True, null=True)),
                ("endpoint", models.CharField(max_length=600, unique=True)),
                ("p256dh", models.CharField(max_length=200)),
                ("auth", models.CharField(max_length=100)),
                (
                    "plataforma",
                    models.CharField(
                        choices=[("android", "Android"), ("ios", "iPhone"), ("outro", "Outro aparelho")],
                        db_index=True,
                        default="outro",
                        help_text="Descoberto pelo próprio aparelho ao se inscrever.",
                        max_length=10,
                    ),
                ),
                ("aparelho", models.CharField(blank=True, max_length=120)),
                ("ultimo_aviso", models.DateTimeField(blank=True, null=True)),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="aparelhos_do_app",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Aparelho de cliente",
                "verbose_name_plural": "Aparelhos de clientes",
                "ordering": ("-criacao", "-id"),
            },
        ),
        migrations.CreateModel(
            name="AvisoDoAplicativo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criacao", models.DateTimeField(auto_now_add=True, null=True)),
                ("atualizado", models.DateTimeField(auto_now=True, null=True)),
                ("titulo", models.CharField(max_length=65)),
                ("mensagem", models.CharField(max_length=240)),
                (
                    "url",
                    models.CharField(
                        blank=True,
                        help_text="Caminho do site, como /loja/ ou /brinquedo/12/.",
                        max_length=300,
                        verbose_name="Endereço ao tocar",
                    ),
                ),
                (
                    "publico",
                    models.CharField(
                        choices=[
                            ("todos", "Todos os aparelhos"),
                            ("android", "Somente Android"),
                            ("ios", "Somente iPhone"),
                        ],
                        default="todos",
                        max_length=10,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("rascunho", "Rascunho"), ("enviado", "Enviado")],
                        db_index=True,
                        default="rascunho",
                        max_length=10,
                    ),
                ),
                ("enviado_em", models.DateTimeField(blank=True, null=True)),
                ("aparelhos_no_envio", models.PositiveIntegerField(default=0)),
                ("entregues", models.PositiveIntegerField(default=0)),
                ("falhas", models.PositiveIntegerField(default=0)),
                (
                    "autor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="avisos_do_app",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Aviso do aplicativo",
                "verbose_name_plural": "Avisos do aplicativo",
                "ordering": ("-criacao", "-id"),
            },
        ),
    ]
