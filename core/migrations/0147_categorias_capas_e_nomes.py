"""As categorias: a Área Ninja (e as outras áreas que faltarem), os nomes e as fotos novas.

SÓ DADOS. O que cada parte faz e por quê está em core/categorias_capas.py:
  * os nomes TODOS em maiúsculas (ou em minúsculas) das categorias, dos
    produtos, das peças e das categorias das peças passam para Maiúsculas e
    Minúsculas ("BOLICHE VIRTUAL" -> "Boliche Virtual"; core/nomes.py); os
    que já têm as duas caixas ficam como estão;
  * as áreas da fábrica que não tinham categoria nascem, se já há produto
    ativo com o nome delas ("Brinquedão Ninja" -> Área Ninja); a Área Baby
    espera um produto "baby"; os produtos de área que estavam fora da
    categoria dela entram (nenhum sai);
  * as fotos de core/static/site/categorias/ sobem para o Cloudinary, só no
    Render (como as fotos da 0142 e da 0143). Se a subida falhar, o deploy
    segue e `python manage.py atualizar_capas_categorias` refaz.
Desfazer não volta os nomes nem apaga as categorias: não há o que desfazer
sem perder o que o painel mudou depois.
"""

from django.db import migrations

from core.categorias_capas import migrar


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0146_air_game_kids_alienigenas"),
    ]

    operations = [
        migrations.RunPython(migrar, migrations.RunPython.noop),
    ]
