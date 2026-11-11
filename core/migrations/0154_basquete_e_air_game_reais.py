"""O Basquete Street Quadrinhos e o Air Game Kids Alienígenas iguais às máquinas de verdade, no site (a 0154).

A seção 61 refez o 3D dos dois (o basquete com o gabinete do Basquete Home,
a rampa com as bolas, a bola vazada nas laterais, o moedeiro, o neon e o
placar; o Air Game com o LED na borda, a régua preta e o placar) e as fotos
do cadastro deles (frente, lados, verso, jogador / tampo). Com o 3D novo,
foram refeitas também as cenas que usam esses .glb (ferramentas/categorias:
`gerar.cjs --glb ...`): as capas em cena dos dois (a da 0153) e as fotos das
categorias onde eles aparecem.

Esta:
  * SÓ NO RENDER (o Cloudinary só está lá): a galeria de cada um dos dois que
    é a que o cadastro subiu (e não fotos postas pelo painel) é refeita À
    FORÇA com as fotos de hoje -- mesmo que a 0153 já tenha posto a capa em
    cena: a capa e as vistas mudaram, com o mesmo nome de arquivo;
  * em todo lugar (só o banco, como a 0150): o objeto 3D é religado ao .glb
    de hoje, com as cores e as medidas dele; um .glb enviado pelo painel
    continua valendo;
  * SÓ NO RENDER: sobem as fotos das categorias que mudaram (as que têm um
    destes .glb; `atualizar_capas`, como a 0152).
Se uma subida falhar, o deploy segue e o aviso diz o comando:
    python manage.py cadastrar_variantes_adesivo --so <chave> --fotos
    python manage.py atualizar_capas_categorias
"""

from django.db import migrations, transaction

from core.cadastro_modelos import migracao_objetos_3d

#: As duas máquinas refeitas (as chaves de core/cadastro_modelos.py, CADASTROS).
CHAVES = ("basquete-street-quadrinhos", "air-game-kids-alienigenas")


def refazer(apps, schema_editor, avisar=print):
    from django.conf import settings

    from core import categorias_capas
    from core.cadastro_modelos import CADASTROS, cadastrar, fotos_do_cadastro

    no_render = getattr(settings, "IS_RENDER", False)
    if no_render:
        Brinquedos = apps.get_model("core", "Brinquedos")
        for chave in CHAVES:
            dados = CADASTROS[chave]
            brinquedo = Brinquedos.objects.filter(nome_brinquedo=dados["nome"]).first()
            if brinquedo is None or not fotos_do_cadastro(brinquedo, chave):
                continue  # fora do catálogo (a ligação abaixo cadastra) ou com as fotos do painel
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
                avisar(f"As fotos do {dados['nome']} agora são as do 3D novo ({len(dados['fotos'])} na galeria).")
            except Exception as erro:  # o deploy segue; o comando refaz depois
                avisar(f"As fotos do {dados['nome']} não foram refeitas agora ({erro!r}). "
                       f"Rode: python manage.py cadastrar_variantes_adesivo --so {chave} --fotos")
    # o objeto 3D com o .glb de hoje (as cores e as medidas), em todo lugar
    for chave in CHAVES:
        migracao_objetos_3d(chave)(apps, schema_editor)
    if no_render:
        # as fotos das categorias com estes .glb (só as que mudaram; se falhar, avisa o comando)
        categorias_capas.subir_fotos_no_deploy(apps, schema_editor, avisar=avisar)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0153_capas_em_cena"),
    ]

    operations = [
        migrations.RunPython(refazer, migrations.RunPython.noop),
    ]
