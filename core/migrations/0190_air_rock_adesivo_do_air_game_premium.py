"""O Air Rock vira um adesivo do Air Game Premium: um objeto só (a 0190; LEIA-ME 72). Só dados.

O cliente: "vc não percebeu que o air game premium e o air game rock são o
mesmo, só é um adesivo? e que eles deveriam estar juntos". A regra da 0169
com a estrutura de hoje (core.variantes.juntar_os_achados_depois): o Air Game
Premium é o produto, com o adesivo padrão "Premium" (a arte dele) e o "Air
Rock"; o adesivo padrão da ficha do Air Rock (a capa em cena do showroom, as
posições, o recorte do cartaz sem tipo e sem papel, fora do site, e o 3D, se
tiver) muda de dono; TODAS as referências (carrinho -- com o adesivo "Air
Rock" --, orçamento, pedido, favorito, lista de desejos, promoção e extras --
a "Black Friday: Air Rock" fica com a arte e o preço --, combo, clique e as
interações por hora das análises) vão para o Air Game Premium; a ficha é
APAGADA (o endereço antigo vai, 301, para o produto). Nada sobe; rodar de
novo não faz nada. A volta não recria a ficha (como a 0169).
"""

from django.db import migrations


def juntar(apps, schema_editor):
    from core import variantes

    variantes.juntar_os_achados_depois(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0186_capas_quadradas_dos_adesivos"),
    ]

    operations = [
        migrations.RunPython(juntar, migrations.RunPython.noop),
    ]
