"""Cadastra o Air Game Hockey Espacial e o Basquete Street Quadrinhos (as máquinas de sempre com os adesivos novos).

São a MESMA máquina do Air Game Hockey e do Basquete Street, só com outra
adesivagem, cada uma com o seu objeto 3D (ferramentas/modelos3d/<id>/). Como
a 0143: o objeto 3D se liga ao brinquedo que já estiver no catálogo (pelo
nome), em todo lugar; se ele ainda não está, no deploy do Render o brinquedo
entra COPIANDO a máquina de antes (preço, voltagem, loja, avaliação, medidas,
categorias e tags; a descrição fala da arte nova), com as cinco fotos vistas
do próprio 3D, que sobem para o Cloudinary. Sem a máquina de antes no
catálogo, entra como as outras (as medidas do projeto, as categorias pelo
nome, sem preço e fora da loja). No computador e nos testes não cadastra
nada; se o Cloudinary falhar, o deploy segue e
`python manage.py cadastrar_variantes_adesivo` refaz. Enquanto isso a Arena
3D já mostra os dois objetos (core/arena.py, MODELOS_3D).
"""

from django.db import migrations

from core.cadastro_modelos import migracao_objetos_3d


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0144_fotos_do_espaco"),
    ]

    operations = [
        migrations.RunPython(
            migracao_objetos_3d("air-game-hockey-espacial", "basquete-street-quadrinhos"),
            migrations.RunPython.noop,
        ),
    ]
