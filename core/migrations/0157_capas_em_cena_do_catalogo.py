"""As capas em cena dos produtos do catálogo (a 0157; LEIA-ME, seção 64).

Os produtos do site cuja capa é a máquina no fundo branco ganham a capa em
cena: a foto da máquina inteira no showroom da Lazer & Sport, quadrada
(core/capas_catalogo.py; as fotos em core/static/site/capas_catalogo/).

O campo `ImagemBrinquedo.papel_na_capa` vem da 0156, num arquivo à parte:
no Postgres, esquema e dados na mesma migração estouram com "pending
trigger events" (sistema_interno/tests_migracoes.py).

SÓ NO RENDER (o Cloudinary só está lá): cada produto da lista cuja capa
ainda é a foto da lista (o public id do Cloudinary) ganha a capa em cena; o
que a equipe já trocou no painel fica. Se a subida de um falhar, o deploy
segue e o aviso diz o comando:
    python manage.py capas_em_cena --so <id>
Para voltar: python manage.py capas_em_cena --desfazer
"""

from django.db import migrations


def subir(apps, schema_editor):
    from core import capas_catalogo

    capas_catalogo.subir_no_deploy(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0156_papel_na_capa"),
    ]

    operations = [
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
