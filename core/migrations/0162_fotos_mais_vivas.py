"""As fotos de produto mais vivas e os furos de verdade nos recortes (a 0162; LEIA-ME, seção 72).

O cliente: "veja se vc consegue deixar mais vivo os brinquedos nas fotos,
recorte bem também o basquete home pq no braço é furado". As capas do
catálogo (core/static/site/capas_catalogo/), as capas e as vistas da galeria
dos nossos 3D foram refeitas com o brinquedo mais vivo (só nele: o fundo fica
como estava; ferramentas/categorias/compor.py, `vivo`); as do Basquete Home,
do Basquete Street e do Air Game Premium, também com o recorte novo (o braço
vazado, a rede sem a parede da loja atrás, o chão sem a sombra do estúdio),
e as fotos de Competitivos e Esportivos, que têm essas máquinas.

SÓ NO RENDER (o Cloudinary só está lá); nada muda no banco fora dele:
  * as capas do catálogo que estão em cena ganham a foto de hoje (a
    assinatura no nome mudou: core/capas_catalogo.py); a capa trocada no
    painel fica;
  * a galeria de cada um dos nossos 3D que é a que o cadastro subiu é
    refeita, como na 0158 (a mesma função), e sobem as fotos das categorias
    que mudaram.
Se uma subida falhar, o deploy segue e o aviso diz o comando:
    python manage.py capas_em_cena
    python manage.py cadastrar_modelo_3d <chave> --fotos
    python manage.py atualizar_capas_categorias
"""

import importlib

from django.db import migrations


def subir(apps, schema_editor):
    from core import capas_catalogo

    # as fotos dos nossos 3D e as categorias: a mesma subida da 0158 (os arquivos mudaram de novo)
    importlib.import_module("core.migrations.0158_fotos_no_showroom").refazer(apps, schema_editor)
    capas_catalogo.subir_no_deploy(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0161_juntar_variantes_de_adesivo"),
    ]

    operations = [
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
