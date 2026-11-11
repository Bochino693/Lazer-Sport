"""O Strike Kids mais vivo e nítido (LEIA-ME, seção 74).

O cliente: "olha como está escuro o brinquedo, faça bem vivo e nítido". A
capa e as vistas da galeria (core/static/site/arena/modelos/strike-kids/)
foram refeitas: os meios-tons da máquina sobem (gama), a cor e a nitidez
também, só onde há cor (o brinquedo); o fundo da cena só ganha nitidez.

SÓ NO RENDER (o Cloudinary só está lá): se a galeria do Strike Kids ainda é
a que o cadastro subiu (e não fotos trocadas no painel), ela é refeita com
as fotos de hoje. Se a subida falhar, o deploy segue e o aviso diz o comando:
    python manage.py cadastrar_modelo_3d strike-kids --fotos
"""

from django.db import migrations, transaction


def refazer(apps, schema_editor):
    from django.conf import settings

    from core.cadastro_modelos import CADASTROS, cadastrar, fotos_do_cadastro

    if not getattr(settings, "IS_RENDER", False):
        return
    chave = "strike-kids"
    Brinquedos = apps.get_model("core", "Brinquedos")
    brinquedo = Brinquedos.objects.filter(nome_brinquedo=CADASTROS[chave]["nome"]).first()
    if brinquedo is None or not fotos_do_cadastro(brinquedo, chave):
        return
    try:
        with transaction.atomic():
            cadastrar(
                chave, Brinquedos, apps.get_model("core", "CategoriasBrinquedos"),
                apps.get_model("core", "ImagemBrinquedo"), refazer_fotos=True, avisar=lambda *_: None,
            )
    except Exception as erro:  # o deploy segue; o comando refaz depois
        print(f"As fotos do Strike Kids não foram refeitas agora ({erro!r}). "
              "Rode: python manage.py cadastrar_modelo_3d strike-kids --fotos")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0163_black_friday_2026"),
    ]

    operations = [
        migrations.RunPython(refazer, migrations.RunPython.noop),
    ]
