"""As posições tiradas do 3D de cada adesivo (a 0174; LEIA-ME 72). Só dados, só no Render.

Sobem como fotos de cada adesivo as vistas do 3D dele, no showroom (nunca de
fundo branco; core.variantes.POSICOES_DO_3D, os arquivos em
core/static/site/arena/modelos/<pasta>/):
  * Air Game Kids, Astronautas (o padrão): em 3/4, o lado direito, o lado
    esquerdo em 3/4, a cabeceira e o tampo de cima (a frente, a capa,
    continua a foto de verdade do catálogo, em cena);
  * Air Game Kids, Alienígenas: o lado esquerdo e a cabeceira refeitos (o
    lado esquerdo era o direito de novo, e o verso, a frente: a mesa é
    simétrica; a vista de antes sai da posição e fica guardada no adesivo);
  * Basquete Home, Quadrinhos: o lado direito refeito (era quase igual ao
    esquerdo), de perto, com o console;
  * Brinquedão Modelo 2 (o padrão): os dois lados, do 3D, no showroom (os de
    antes eram a folha da fábrica, de fundo branco: viraram recorte para
    artes na 0173).
Nunca troca a foto que alguém pôs numa posição; rodar de novo não sobe nada
outra vez. Só no Render (o Cloudinary só está lá); se a subida falhar, o
deploy segue e o comando refaz:
    python manage.py posicoes_dos_adesivos
A volta não apaga nada (as fotos ficam no adesivo).
"""

from django.db import migrations


def subir(apps, schema_editor):
    from core import variantes

    variantes.subir_posicoes_no_deploy(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0173_adesivo_padrao_de_todo_brinquedo"),
    ]

    operations = [
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
