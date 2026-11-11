"""Um objeto só no banco (a 0169; LEIA-ME, seção 72). Só dados, em todo lugar, numa transação por par.

O cliente: "POR ENQUANTO SÓ TEM DOIS OBJETOS ... DEVE MUDAR A ESTRUTURA DOS
OBJETOS, DEIXAR SOMENTE UM MAS COM O OUTRO ADESIVO E SEU RESPECTIVO OBJETO 3D
... ALÉM DO MAIS MUDE O VALOR PARA 6990,00 DO AIR GAME". Para cada adesivo que
ainda aponta para um produto à parte (o Air Game Kids Alienígenas no Air Game
Kids, o Basquete Home Quadrinhos no Basquete Home), core.variantes.estruturar:
  * o 3D do produto à parte passa para o adesivo (o mesmo .glb: nada sobe);
  * as fotos dele viram fotos do produto, do adesivo (`ImagemBrinquedo.
    variante`; os mesmos arquivos do Cloudinary);
  * TODAS as referências a ele passam para o produto -- achadas pelas
    relações que apontam para Brinquedos (orçamentos e itens, promoções e
    brinquedos extras, combos, eventos, cupons, favoritos, listas de desejos,
    cliques, manutenções, materiais, a composição...) e pelas chaves
    genéricas (o item do carrinho, que fica com o adesivo; o item do pedido).
    O repetido (o favorito do mesmo usuário) vira um só; a mesma linha no
    carrinho soma a quantidade;
  * o produto à parte é APAGADO; o id dele fica no adesivo (`id_antigo`) e o
    endereço antigo redireciona (301) para o produto.
O Air Game Kids fica com R$ 6.990,00. Rodar de novo não faz nada. A 0170 tira
o `origem` do adesivo (esquema, em arquivo próprio).
"""

from django.db import migrations


def estruturar(apps, schema_editor):
    from core import variantes

    variantes.estruturar(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0168_variantes_donas_do_3d_e_das_fotos"),
        ("sistema_interno", "0057_orcamento_valor_final"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(estruturar, migrations.RunPython.noop),
    ]
