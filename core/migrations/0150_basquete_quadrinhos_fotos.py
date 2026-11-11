"""O Basquete Street Quadrinhos com as fotos e o 3D da arte de verdade (a 0150).

A 0145 subiu ao site junto com a PRIMEIRA versão do Basquete Street
Quadrinhos, a de arte provisória (a rede em cima, os bonecos com 7 e 10,
os "WOW!" desenhados aqui). Logo depois o objeto foi refeito com a folha
de adesivos da fábrica -- a forma e a arte de verdade --, mas no Render a
0145 já tinha rodado: o cadastro ficou com as fotos da versão provisória,
e o cliente via no card uma máquina que não é a dele. (A 0146 só refez as
fotos do Air Game.)

Esta, SÓ NO RENDER (o Cloudinary só está lá): se a galeria do Basquete
Street Quadrinhos é a que o cadastro subiu (e não fotos postas pelo
painel), ela é trocada pelas vistas do 3D de hoje. Em todo lugar, o objeto
3D é religado ao .glb de hoje (com as cores e as medidas dele); um .glb
enviado pelo painel continua valendo. Se a subida falhar, o deploy segue e
    python manage.py cadastrar_variantes_adesivo --so basquete-street-quadrinhos --fotos
refaz.
"""

from django.db import migrations, transaction

from core.cadastro_modelos import migracao_objetos_3d

CHAVE = "basquete-street-quadrinhos"


def refazer(apps, schema_editor):
    from django.conf import settings

    from core.cadastro_modelos import CADASTROS, cadastrar, fotos_do_cadastro

    if getattr(settings, "IS_RENDER", False):
        Brinquedos = apps.get_model("core", "Brinquedos")
        brinquedo = Brinquedos.objects.filter(nome_brinquedo=CADASTROS[CHAVE]["nome"]).first()
        if brinquedo is not None and fotos_do_cadastro(brinquedo, CHAVE):
            try:
                with transaction.atomic():
                    cadastrar(
                        CHAVE,
                        Brinquedos,
                        apps.get_model("core", "CategoriasBrinquedos"),
                        apps.get_model("core", "ImagemBrinquedo"),
                        refazer_fotos=True,
                    )
            except Exception as erro:  # o deploy segue; o comando refaz depois
                print(f"As fotos do {CADASTROS[CHAVE]['nome']} não foram refeitas agora ({erro!r}). "
                      f"Rode: python manage.py cadastrar_variantes_adesivo --so {CHAVE} --fotos")
    migracao_objetos_3d(CHAVE)(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0149_categorias_nos_lugares"),
    ]

    operations = [
        migrations.RunPython(refazer, migrations.RunPython.noop),
    ]
