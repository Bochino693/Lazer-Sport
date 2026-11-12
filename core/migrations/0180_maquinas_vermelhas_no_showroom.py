"""As máquinas da Black Friday no showroom (a 0180; LEIA-ME, seção 78).

O cliente, com o print do card do Basquete Kids (a máquina no fundo de neon
vermelho do cartaz da Black Friday): "veja que o fundo não ficou uniforme com
o que preciso, de paisagens e tal ... identifique as máquinas com o fundo
vermelho e ponha elas no padrão". E, com o do Air Rock (a foto panorâmica
cortada no card quadrado): "valide para não ter fotos assim com zoom pois
estraga".

Os produtos que a Black Friday criou (a 0163) tinham a capa recortada do
cartaz: Basquete Duplo, Basquete Kids e as três casinhas no neon vermelho; o
Air Rock e o Kid Play, panorâmicos. Cada um ganha a capa em cena, como as do
catálogo (a 0157): a máquina inteira no showroom, quadrada
(core/static/site/capas_catalogo/<chave>.webp). O recorte do cartaz fica
cadastrado, mas fora da galeria pública (core/capas_catalogo.py, VERMELHAS).
A categoria "Casinhas Cenográficas" ganha a foto das três casinhas na
brinquedoteca, com as crianças (core/static/site/categorias/).

SÓ DADOS (nenhum campo novo: o `papel_na_capa` vem da 0156) e SÓ NO RENDER (o
Cloudinary só está lá). Rodar de novo não muda nada; o produto (ou a
categoria) cuja foto a equipe já trocou no painel fica como está. Se uma
subida falhar, o deploy segue e o aviso diz o comando:
    python manage.py capas_em_cena --vermelhas      (ou --so <id>)
Para voltar: python manage.py capas_em_cena --vermelhas --desfazer
"""

from django.db import migrations


def subir(apps, schema_editor):
    from core import capas_catalogo

    capas_catalogo.vermelhas_no_deploy(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0175_kit_sucesso_com_matrix"),
    ]

    operations = [
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
