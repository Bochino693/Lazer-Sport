"""A capa quadrada de cada adesivo dos nossos 3D (a 0186; LEIA-ME, seção 80).

O cliente: "de novo vc errou no dimensionamento de algumas fotos, elas devem
ser padrão. veja que não quero fotos cortadas menores, deve seguir o mesmo
padrão." Todo card mostra a capa QUADRADA (1600 x 1600), com a máquina
inteira no showroom. Fugiam: os adesivos Alienígenas (Air Game Kids) e
Quadrinhos (Basquete Home), cuja primeira foto era a vista do 3D de 1600 x
1000, e os Brinquedões Modelo 4 e 5 (a imagem da fábrica). Cada um ganha a
capa do 3D dele (core/static/site/arena/modelos/<chave>/capa.webp) como a
frente do adesivo, marcada `papel_na_capa = "cena"`; a do padrão é também a
capa do produto. A imagem da fábrica continua na galeria (em outra posição).
Os nossos 3D de um adesivo só (a capa do cadastro já é quadrada) só ganham o
papel "cena" (core/capas_quadradas.py, ITENS).

SÓ DADOS (nenhum campo novo) e SÓ NO RENDER (o Cloudinary só está lá).
Rodar de novo não muda nada; o adesivo cuja frente a equipe trocou no painel
fica como está. Se uma subida falhar, o deploy segue e o aviso diz o comando:
    python manage.py capas_em_cena --quadradas      (ou --so "<produto>")
Para voltar: python manage.py capas_em_cena --quadradas --desfazer
"""

from django.db import migrations


def subir(apps, schema_editor):
    from core import capas_quadradas

    capas_quadradas.no_deploy(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0185_fotos_sem_fundo_fora_do_site"),
    ]

    operations = [
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
