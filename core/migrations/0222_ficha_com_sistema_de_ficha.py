"""A ficha "Air Game Premium com Sistema de Ficheiro" vira a OPÇÃO do Air Game Premium (a 0222;
LEIA-ME-V10, seção 151). Só dados.

O dono: "deve se chamar sistema de ficha" e o acréscimo é um só (R$ 999,00). A ficha à parte
(#46 no ar, R$ 14.990,00) é a mesma máquina com sistema de ficha: as referências passam para o
Air Game Premium com a opção marcada, a ficha é apagada e o endereço antigo redireciona. O preço
passa a ser Air Game Premium + o acréscimo; o LOG DO DEPLOY diz o preço antigo e o novo.

A regra mora em core/variantes.py (`unir_as_fichas_com_sistema_de_ficha`). A ficha é achada pelo
NOME, exatamente: com outro nome no ar, nada muda e o log diz "ficha não encontrada". Rodar de
novo não faz nada. A volta não recria a ficha (como a 0218).
"""

from django.db import migrations


def unir(apps, schema_editor):
    from core import variantes

    variantes.unir_as_fichas_com_sistema_de_ficha(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0221_item_do_carrinho_com_sistema_de_ficha"),
        # o item do orçamento com a opção (`com_moedeiro`) e o acréscimo de R$ 999,00
        ("sistema_interno", "0087_item_do_orcamento_com_sistema_de_ficha"),
    ]

    operations = [
        migrations.RunPython(unir, migrations.RunPython.noop),
    ]
