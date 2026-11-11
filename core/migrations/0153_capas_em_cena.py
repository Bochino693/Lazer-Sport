"""A capa dos nossos produtos em 3D vira uma cena cheia (a 0153).

O cliente: "as fotos nas categorias devem ficar full ali, sem as bordas
brancas". A CAPA de um produto -- a foto do card de produto (a
`imagem_brinquedo`) e a primeira da galeria -- era a vista do 3D num fundo
claro. Agora é uma cena quadrada, como as fotos das categorias: o produto
inteiro e grande num lugar que combina com ele, com a criançada e a luz
(ferramentas/categorias: as cenas "capa:<chave>"; o arquivo é o capa.webp
na pasta de cada um, a primeira foto de CADASTROS[chave]["fotos"]). A vista
que era a capa fica na galeria, sem tipo. O Brinquedão Modelo 5 passa a ter
de capa a foto do salão da fábrica; o Modelo 4 fica como está.

Esta, SÓ NO RENDER (o Cloudinary só está lá): a galeria de cada um destes
produtos que está no catálogo com as fotos que o cadastro subiu (e não
fotos postas pelo painel) é refeita com as de hoje -- uma vez: com a capa
de hoje, não sobe nada. Se a subida de um falhar, o deploy segue e
    python manage.py cadastrar_modelo_3d <chave> --fotos
refaz (o aviso diz qual).
"""

from pathlib import Path

from django.db import migrations, transaction

#: Os produtos com a capa nova (as chaves de core/cadastro_modelos.py, CADASTROS).
CHAVES = (
    "brinquedao-modelo-2",
    "brinquedao-modelo-3",
    "brinquedao-ninja",
    "brinquedao-modelo-5",
    "espaco-esportivo-modelo-1",
    "trampolim-enterrada",
    "strike-kids",
    "air-game-kids-alienigenas",
    "basquete-street-quadrinhos",
)


def refazer(apps, schema_editor, avisar=print):
    from django.conf import settings

    from core.cadastro_modelos import CADASTROS, cadastrar, fotos_do_cadastro

    if not getattr(settings, "IS_RENDER", False):
        return
    Brinquedos = apps.get_model("core", "Brinquedos")
    for chave in CHAVES:
        dados = CADASTROS[chave]
        brinquedo = Brinquedos.objects.filter(nome_brinquedo=dados["nome"]).first()
        if brinquedo is None or not fotos_do_cadastro(brinquedo, chave):
            continue  # fora do catálogo (outra migração cadastra) ou com as fotos do painel
        capa = f"{chave}-{Path(dados['fotos'][0][0]).stem}"
        if capa in (brinquedo.imagem_brinquedo.name or ""):
            continue  # já tem a capa de hoje
        try:
            with transaction.atomic():
                cadastrar(
                    chave,
                    Brinquedos,
                    apps.get_model("core", "CategoriasBrinquedos"),
                    apps.get_model("core", "ImagemBrinquedo"),
                    refazer_fotos=True,
                    avisar=lambda *_: None,
                )
            avisar(f"A capa do {dados['nome']} agora é a cena ({dados['fotos'][0][0]}).")
        except Exception as erro:  # o deploy segue; o comando refaz depois
            avisar(f"A capa do {dados['nome']} não foi trocada agora ({erro!r}). "
                   f"Rode: python manage.py cadastrar_modelo_3d {chave} --fotos")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0152_categorias_maquinas_reais"),
    ]

    operations = [
        migrations.RunPython(refazer, migrations.RunPython.noop),
    ]
