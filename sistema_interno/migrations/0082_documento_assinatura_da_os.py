"""A ordem de serviço assinada no celular (LEIA-ME-V10, seção 124).

Só esquema: o documento de assinatura passa a nascer também da O.S.
(`ordem_servico`, PROTECT como o do orçamento: o assinado é a prova do
serviço contratado), o orçamento fica opcional e uma regra no banco diz
que cada documento tem UMA origem -- o orçamento ou a O.S. Os documentos
que já existem são todos de orçamento e continuam como estão.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0081_documento_ordem_servico"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="documentoassinatura",
            name="ordem_servico",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documentos_assinatura",
                to="sistema_interno.ordemservico",
            ),
        ),
        migrations.AlterField(
            model_name="documentoassinatura",
            name="orcamento",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documentos_assinatura",
                to="sistema_interno.orcamento",
            ),
        ),
        migrations.AddConstraint(
            model_name="documentoassinatura",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("orcamento__isnull", False), ("ordem_servico__isnull", True)
                    ),
                    models.Q(
                        ("orcamento__isnull", True), ("ordem_servico__isnull", False)
                    ),
                    _connector="OR",
                ),
                name="documento_assinatura_uma_origem",
            ),
        ),
    ]
