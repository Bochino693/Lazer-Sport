"""O automatizador da O.S. (LEIA-ME-V10, seção 122): o documento de origem.

Só esquema: DocumentoOrdemServico -- o arquivo original (cofre privado),
quem enviou, a leitura e o elo com a O.S. criada. O SHA-256 do arquivo é
único no banco (índice parcial, fora o vazio): o mesmo documento não vira
duas O.S., nem com dois envios ao mesmo tempo.
"""

import django.db.models.deletion
import sistema_interno.importacao_os.armazenamento
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0080_diario_de_bordo_da_assinatura"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentoOrdemServico",
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
                            ("pendente", "Falta completar"),
                            ("criada", "O.S. criada"),
                        ],
                        db_index=True,
                        default="pendente",
                        max_length=10,
                    ),
                ),
                (
                    "formato",
                    models.CharField(
                        choices=[
                            ("docx", "Word (.docx)"),
                            ("pdf", "PDF"),
                            ("txt", "Texto (.txt)"),
                        ],
                        max_length=4,
                    ),
                ),
                (
                    "arquivo",
                    models.FileField(
                        blank=True,
                        storage=sistema_interno.importacao_os.armazenamento.ArmazenamentoDosDocumentosOS(),
                        upload_to=sistema_interno.importacao_os.armazenamento.caminho_do_documento,
                    ),
                ),
                ("nome_arquivo", models.CharField(blank=True, max_length=150)),
                ("tamanho_arquivo", models.PositiveIntegerField(default=0)),
                ("sha256", models.CharField(db_index=True, max_length=64)),
                (
                    "texto_sha256",
                    models.CharField(blank=True, db_index=True, max_length=64),
                ),
                (
                    "numero_no_documento",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        max_length=40,
                        verbose_name="número de O.S. escrito no documento",
                    ),
                ),
                ("leitura", models.JSONField(blank=True, default=dict)),
                (
                    "enviado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "ordem",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documentos",
                        to="sistema_interno.ordemservico",
                    ),
                ),
            ],
            options={
                "verbose_name": "Documento de ordem de serviço",
                "verbose_name_plural": "Documentos de ordens de serviço",
                "ordering": ("-criacao", "-id"),
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("sha256", ""), _negated=True),
                        fields=("sha256",),
                        name="documento_os_sha256_unico",
                    )
                ],
            },
        ),
    ]
