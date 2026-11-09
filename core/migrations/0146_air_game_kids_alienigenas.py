"""O Air Game Hockey Espacial da 0145 vira o Air Game Kids Alienígenas.

A folha de adesivos dos alienígenas é a do Air Game Kids (a mesa infantil de
formato recortado, 0,90 x 0,86 x 1,50 m), não a do Air Game Hockey: o produto
muda de nome e de base, e o objeto 3D foi refeito na altura de 0,90 m
(site/arena/modelos/air-game-kids-alienigenas.glb; o .glb de antes não existe
mais). A 0145 fica como está (num banco novo ela já cadastra o novo, pelo
apelido da chave antiga em core/cadastro_modelos.py). Esta, onde a 0145 já
rodou (`renomear_variante`, em todo lugar, só o banco):
  * o "Air Game Hockey Espacial" ganha o nome novo, a descrição nova e, do
    Air Game Kids do catálogo, o preço, a avaliação, a loja, a voltagem, as
    medidas, as categorias e as tags (sem ele, as medidas do projeto; o resto
    fica como está);
  * as descrições das fotos passam a dizer o nome novo;
  * o objeto 3D dele passa para o código e o .glb novos (com as cores e as
    medidas do .glb novo).
No Render, as fotos que a 0145 subiu (vistas do 3D de antes) são trocadas
pelas de hoje (sobem para o Cloudinary). E, como a 0145: se a máquina não
está no catálogo, no Render ela é cadastrada; nos outros lugares o objeto 3D
só se liga a quem já está. Se a subida falhar, o deploy segue e
`python manage.py cadastrar_variantes_adesivo --so air-game-kids-alienigenas --fotos`
refaz. Rodar de novo não faz nada.
"""

from django.db import migrations

from core.cadastro_modelos import migracao_renomear_variante


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0145_variantes_de_adesivo"),
    ]

    operations = [
        migrations.RunPython(
            migracao_renomear_variante("air-game-hockey-espacial", "Air Game Hockey Espacial"),
            migrations.RunPython.noop,
        ),
    ]
