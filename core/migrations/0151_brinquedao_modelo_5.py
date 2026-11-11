"""Cadastra o Brinquedão Modelo 5 (o objeto 3D feito com as quatro imagens do projeto).

O brinquedão pequeno de tubos cor de madeira em L: 3,70 m × 1 m, altura de
2 m, o piso a 1 m. Como a 0143: o objeto 3D se liga ao brinquedo que já
estiver no catálogo (pelo nome), em todo lugar; se ele ainda não está, no
deploy do Render o brinquedo entra fora da loja, na categoria Brinquedão,
com as oito fotos (a perspectiva da fábrica de principal, as quatro vistas
do 3D, a planta e as duas vistas do salão), que sobem para o Cloudinary. No
computador e nos testes não cadastra nada; se a subida falhar, o deploy
segue e avisa: `python manage.py cadastrar_modelo_3d brinquedao-modelo-5`
(ou `cadastrar_brinquedao_modelo_5`) refaz. Enquanto isso a Arena 3D já
mostra o objeto (core/arena.py, MODELOS_3D).
"""

from django.db import migrations

from core.cadastro_modelos import migracao_objetos_3d


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0150_basquete_quadrinhos_fotos"),
    ]

    operations = [
        migrations.RunPython(migracao_objetos_3d("brinquedao-modelo-5"), migrations.RunPython.noop),
    ]
