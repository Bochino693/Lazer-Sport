# O CÓDIGO DO ORÇAMENTO (LEIA-ME-V10, seção 104).
#
# SÓ ESQUEMA: com todos os orçamentos já com código (0066), a coluna vira
# ÚNICA e OBRIGATÓRIA, e o orçamento novo nasce com o sorteio
# (`gerar_codigo_orcamento`). Único porque o código é o que o cliente
# digita em Meus pedidos: dois orçamentos com o mesmo código seriam uma
# porta aberta para a proposta de outra pessoa.

import sistema_interno.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0066_codigos_dos_orcamentos"),
    ]

    operations = [
        migrations.AlterField(
            model_name="orcamento",
            name="codigo",
            field=models.CharField(
                default=sistema_interno.models.gerar_codigo_orcamento,
                editable=False,
                help_text="O que o cliente digita em Meus pedidos, no site.",
                max_length=12,
                unique=True,
                verbose_name="Código do orçamento",
            ),
        ),
    ]
