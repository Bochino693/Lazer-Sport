"""Um objeto só por produto, com os dois 3D (a 0166; LEIA-ME, seção 72). Só dados.

O cliente: "vc deve deixar apenas um objeto ... como no boliche", "EU QUERO OS
DOIS OBJETOS 3D, NO MESMO BRINQUEDO" e "o basquete home não tem medidas, copie
as medidas do outro que tem". Em cada produto com outra arte
(core.variantes.unificar), em todo lugar:
  * as fotos da ficha juntada (a galeria pública dela) entram na galeria do
    produto, depois das dele, apontando para os MESMOS arquivos (nada sobe
    para o Cloudinary; `papel_na_capa = "outra_arte"`);
  * as medidas que faltam no produto vêm da ficha (o Basquete Home fica com
    as do Basquete Home Quadrinhos: 2,70 x 1,00 x 2,40 m); as que ele já tem
    ficam;
  * o Air Game Kids, sem 3D próprio, ganha o dos Astronautas
    (site/arena/modelos/air-game-kids-astronautas.glb, feito do mesmo móvel do
    Alienígenas); o 3D da ficha continua nela, e os dois aparecem no produto.
Nada é apagado nem trocado; rodar de novo não duplica. O preço não muda.
"""

from django.db import migrations


def unificar(apps, schema_editor):
    from core import variantes

    variantes.unificar_todos(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0165_papel_outra_arte"),
    ]

    operations = [
        migrations.RunPython(unificar, migrations.RunPython.noop),
    ]
