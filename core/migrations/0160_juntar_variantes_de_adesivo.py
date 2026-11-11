"""O Air Game Kids e o Air Game Kids Alienígenas viram um produto só (a 0160; LEIA-ME, seção 72).

O cliente: "os dois devem se tornar o mesmo objeto, como um adesivo
diferente". O Air Game Kids (os astronautas, as fotos dele) é o produto, com
o adesivo padrão "Astronautas"; o Air Game Kids Alienígenas vira o adesivo
"Alienígenas" (as fotos e o .glb dele) e sai das listas: fica desativado, sem
apagar nada (pedidos, orçamentos e favoritos continuam apontando para ele), e
o endereço dele redireciona para o Air Game Kids com ?adesivo=alienigenas.

Em todo lugar (só o banco: nada sobe para o Cloudinary). Pode rodar de novo.
Sem o Air Game Kids no catálogo, não faz nada. Desfazer: core.variantes.separar.
O Basquete Street e o Basquete Street Quadrinhos NÃO entram (a folha de
adesivos do Quadrinhos é a do gabinete do Basquete Home, não a do Basquete
Street: LEIA-ME, seção 72).
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
