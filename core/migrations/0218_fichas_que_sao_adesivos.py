"""As fichas salvas como brinquedo que eram ADESIVOS (a 0218; LEIA-ME-V10, seção 143). Só dados.

O dono: "foi salvo uns brinquedos que na verdade eram para ser adesivos, air
game kids adesivo cand, balde e xícara também... apaga os objetos e adicione
como adesivo." O adesivo se chama "Candy" e não tem preço próprio.

  * "Air Game Kids cand"  -> o adesivo "Candy" do Air Game Kids;
  * "Multijogos 32""      -> o adesivo "Candy" do Multi Jogos;
  * "Balde giratório" e "Balde Giratório Manual" -> UM produto, "Balde
    Giratório", a R$ 8.500,00, com as fotos, as medidas e a voltagem da ficha
    "Manual"; as fotos dela são o adesivo "Candy".

As fotos, o 3D e TODAS as referências (orçamento, carrinho, pedido, favorito,
promoção, combo...) passam para o produto que fica; a ficha à parte é apagada
e o endereço antigo redireciona. A regra mora em core/variantes.py
(`juntar_as_fichas_que_sao_adesivos`, `unir_as_fichas_repetidas`). A ficha é
achada pelo NOME, exatamente: com outro nome no ar, aquele par não muda. Nada
sobe; rodar de novo não faz nada. A volta não recria as fichas (como a 0190).
"""

from django.db import migrations


def juntar(apps, schema_editor):
    from core import variantes

    variantes.juntar_as_fichas_que_sao_adesivos(apps, schema_editor)
    variantes.unir_as_fichas_repetidas(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0217_sinal_do_site"),
    ]

    operations = [
        migrations.RunPython(juntar, migrations.RunPython.noop),
    ]
