"""As fotos das categorias dentro de lugares de verdade (o buffet, o shopping, a game zone...).

O cliente pediu: "enriqueça mais as fotos das categorias, estão muito
brancas, ponha em lugares, shoppings, parques, buffets entre outros." As
16 fotos de core/static/site/categorias/ foram refeitas com os brinquedos
dentro de um lugar montado em 3D (ferramentas/categorias/lugares.js).

SÓ NO RENDER (o Cloudinary só está lá; no computador e nos testes não faz
nada): as fotos de todas as categorias sobem, e só as que mudaram (o nome
do arquivo leva a assinatura do conteúdo). Se a subida falhar, o deploy
segue, e `python manage.py atualizar_capas_categorias` refaz.
"""

from django.db import migrations

from core.categorias_capas import subir_fotos_no_deploy


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0148_air_game_kids_sem_tabua"),
    ]

    operations = [
        migrations.RunPython(subir_fotos_no_deploy, migrations.RunPython.noop),
    ]
