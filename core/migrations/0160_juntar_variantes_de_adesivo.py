"""Os pares de adesivos viram um produto só (a 0160; LEIA-ME, seção 72).

O cliente: "os dois devem se tornar o mesmo objeto, como um adesivo
diferente". Cada par (core.variantes.PARES):
  * o Air Game Kids (os astronautas, as fotos dele) é o produto, com o adesivo
    padrão "Astronautas"; o Air Game Kids Alienígenas vira o adesivo
    "Alienígenas" (as fotos e o .glb dele);
  * o Basquete Home (o gabinete azul) é o produto, com o adesivo padrão
    "Azul"; o "Basquete Street Quadrinhos" -- que é o gabinete do Basquete
    Home com a folha em quadrinhos (LEIA-ME 61) -- antes ganha o nome de hoje,
    "Basquete Home Quadrinhos" (com as descrições das fotos), e vira o adesivo
    "Quadrinhos" (as fotos e o .glb dele). O Basquete Street fica sozinho.
A ficha que vira adesivo sai das listas: fica desativada, sem apagar nada
(pedidos, orçamentos e favoritos continuam apontando para ela), e o endereço
dela redireciona para o produto com ?adesivo=<slug>.

Em todo lugar (só o banco: nada sobe para o Cloudinary). Pode rodar de novo.
Sem o produto no catálogo, aquele par não faz nada. Desfazer:
core.variantes.separar (o nome de hoje fica).
"""

from django.db import migrations


def juntar(apps, schema_editor):
    from core import variantes

    variantes.migrar(apps, schema_editor)


def separar(apps, schema_editor):
    from core import variantes

    for (produto, _padrao), _fichas in variantes.PARES:
        variantes.separar(produto, apps.get_model("core", "Brinquedos"), apps.get_model("core", "VarianteAdesivo"))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0159_variantes_de_adesivo"),
    ]

    operations = [
        migrations.RunPython(juntar, separar),
    ]
