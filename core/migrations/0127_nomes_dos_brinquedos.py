"""Corrige três nomes do catálogo: o Flappy Bird e os dois "PIMBAL".

SÓ DADOS. "FLAPYY BIRD" vira "FLAPPY BIRD", e os dois brinquedos que se
chamavam só "PIMBAL" passam a dizer qual é qual: "PINBALL 32 POLEGADAS" e
"PINBALL 40 POLEGADAS" (é o que as descrições e as telas de cada um dizem).

Mesma cautela da 0126: confere pelo id do site no ar, troca só se o nome
ainda for o antigo, e nos pinballs confere também a tela na descrição --
assim, num banco em que esses ids são de outros brinquedos, nada muda. A
Arena 3D reconhece "pinball" e "pimbal" do mesmo jeito (core/arena.py).
Desfazer volta os nomes antigos.
"""

from django.db import migrations

#: id -> (nome antigo, nome novo, trecho que a descrição tem de ter, ou "")
RENOMES = {
    24: ("FLAPYY BIRD", "FLAPPY BIRD", ""),
    18: ("PIMBAL", "PINBALL 32 POLEGADAS", "32"),
    19: ("PIMBAL", "PINBALL 40 POLEGADAS", "40"),
}


def _igual(a, b):
    return " ".join((a or "").split()).casefold() == " ".join((b or "").split()).casefold()


def _renomear(apps, de, para):
    Brinquedos = apps.get_model("core", "Brinquedos")
    for pk, (antigo, novo, trecho) in RENOMES.items():
        nomes = {"antigo": antigo, "novo": novo}
        brinquedo = Brinquedos.objects.filter(pk=pk).only("id", "nome_brinquedo", "descricao").first()
        if brinquedo is None or not _igual(brinquedo.nome_brinquedo, nomes[de]):
            continue
        if trecho and trecho not in (brinquedo.descricao or ""):
            continue
        Brinquedos.objects.filter(pk=pk).update(nome_brinquedo=nomes[para])


def aplicar(apps, schema_editor):
    _renomear(apps, "antigo", "novo")


def desfazer(apps, schema_editor):
    _renomear(apps, "novo", "antigo")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0126_descricoes_dos_brinquedos"),
    ]

    operations = [
        migrations.RunPython(aplicar, desfazer),
    ]
