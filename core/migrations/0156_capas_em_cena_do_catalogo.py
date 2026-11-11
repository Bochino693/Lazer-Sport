"""As capas em cena dos produtos do catálogo (a 0156; LEIA-ME, seção 64).

Os produtos do site cuja capa é a máquina no fundo branco ganham a capa em
cena: a foto da máquina inteira no showroom da Lazer & Sport, quadrada
(core/capas_catalogo.py; as fotos em core/static/site/capas_catalogo/).

Em todo lugar: o campo `ImagemBrinquedo.papel_na_capa` (a capa em cena e a
capa de antes dela, que continua na galeria e é a que o `--desfazer` põe de
volta).

SÓ NO RENDER (o Cloudinary só está lá): cada produto da lista cuja capa
ainda é a foto da lista (o public id do Cloudinary) ganha a capa em cena; o
que a equipe já trocou no painel fica. Se a subida de um falhar, o deploy
segue e o aviso diz o comando:
    python manage.py capas_em_cena --so <id>
Para voltar: python manage.py capas_em_cena --desfazer
"""

from django.db import migrations, models


def subir(apps, schema_editor):
    from core import capas_catalogo

    capas_catalogo.subir_no_deploy(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0155_imagens_em_alta"),
    ]

    operations = [
        migrations.AddField(
            model_name="imagembrinquedo",
            name="papel_na_capa",
            field=models.CharField(
                blank=True,
                choices=[("cena", "A capa em cena"), ("original", "A capa de antes da cena")],
                default="",
                help_text="Preenchido pelo comando capas_em_cena: a capa em cena e a capa de antes dela.",
                max_length=10,
                verbose_name="Papel na capa em cena",
            ),
        ),
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
