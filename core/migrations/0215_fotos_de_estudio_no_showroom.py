"""As fotos de estúdio refeitas no SHOWROOM da Lazer & Sport (LEIA-ME V10, seção 118). SÓ DADOS.

O dono, com o print do catálogo (o card do Air Game Kids Alienígenas e os dos basquetes com o
fundo azul liso do estúdio): "esses brinquedos com o fundo azul devem ser de ambiente como
falei, nada de fundos singulares." As fotos da seção 96 (Basquete Home Quadrinhos e azul, Air
Game Kids Astronautas e Alienígenas, Strike Kids: as capas e as vistas da galeria) foram refeitas
no Blender com o showroom montado em volta da máquina (ferramentas/fotos3d/showroom.py), nos
MESMOS arquivos do site e com o MESMO enquadramento de cada máquina.

O mecanismo é o da 0197 (core/fotos_estudio.py, `no_deploy`): cada posição que está com a foto
de estúdio de antes (`estudio-<pasta>-<vista>-<assinatura>`) recebe a de hoje na MESMA linha --
a assinatura nova no nome: só a que mudou sobe; rodar de novo não sobe nada --; a capa do
adesivo padrão continua sendo a capa do produto; a foto que a equipe pôs no painel fica; o cache
é limpo. SÓ NO RENDER (o Cloudinary só está lá); fora dele não faz nada. Se a subida falhar, o
deploy segue e o aviso diz o comando:
    python manage.py fotos_de_estudio
A volta não faz nada (as azuis saíram do repositório; o comando com --desfazer volta às fotos de
antes da 0197, se for o caso).
"""

from django.db import migrations


def subir(apps, schema_editor):
    from core import fotos_estudio

    fotos_estudio.no_deploy(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0214_capas_novas_dos_kits"),
    ]

    operations = [
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
