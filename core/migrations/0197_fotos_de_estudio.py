"""As fotos de estúdio do Basquete Home, do Air Game Kids e do Strike Kids (a 0197; LEIA-ME, seção 96).

O chefe: "como o McDonald's: você olha a foto do lanche e quer comer, porque tem vida e
nitidez. As nossas estão apagadas, sem vida; os fundos parecem muito falsos" e "o Basquete
Home normal e o preto: a máquina encolheu". As fotos foram refeitas no estúdio do Blender
(ferramentas/fotos3d/), com um enquadramento só por máquina; os arquivos do site são os
mesmos de antes, com a foto nova.

SÓ DADOS (nenhum campo novo) e SÓ NO RENDER (o Cloudinary só está lá): em cada adesivo, a
posição que está com a NOSSA foto de antes (ou vazia) ganha a foto de estúdio, que sobe com
o nome `estudio-<pasta>-<vista>-<assinatura>` (só a que mudou sobe; rodar de novo não sobe
nada); a de antes fica guardada no adesivo, fora da galeria; a foto que a equipe pôs no
painel fica como está; o cache é limpo. Se uma subida falhar, o deploy segue e o aviso diz o
comando:
    python manage.py fotos_de_estudio
A volta tira as fotos de estúdio e põe as de antes nas posições (core/fotos_estudio.py).
"""

from django.db import migrations


def subir(apps, schema_editor):
    from core import fotos_estudio

    fotos_estudio.no_deploy(apps, schema_editor)


def voltar(apps, schema_editor):
    from core import fotos_estudio

    fotos_estudio.volta_do_deploy(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0196_fotos_das_categorias_no_salao"),
    ]

    operations = [
        migrations.RunPython(subir, voltar),
    ]
