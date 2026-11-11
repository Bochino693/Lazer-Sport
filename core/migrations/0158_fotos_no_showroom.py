"""As fotos dos nossos 3D no showroom e as categorias de hoje (a 0158; LEIA-ME, seção 64).

O cliente: "faça padrão para todas as imagens 2D". As capas e as vistas da
galeria dos nossos produtos em 3D (frente, lados, verso, tampo, jogador...)
foram refeitas no showroom da Lazer & Sport, com a luz de estúdio, com o mesmo
nome de arquivo; o Espaço Esportivo Modelo 1, do alto, no galpão. As fotos das
categorias foram refeitas com o mesmo acabamento (o tone mapping neutro;
Eletrônicos e Fliperama no showroom).

SÓ NO RENDER (o Cloudinary só está lá):
  * a galeria de cada um dos nossos 3D que é a que o cadastro subiu (e não
    fotos postas pelo painel) é refeita À FORÇA (o nome do arquivo é o mesmo:
    as migrações de antes não subiriam de novo);
  * sobem as fotos das categorias que mudaram (`atualizar_capas`).
Se uma subida falhar, o deploy segue e o aviso diz o comando:
    python manage.py cadastrar_modelo_3d <chave> --fotos
    python manage.py atualizar_capas_categorias
"""

from django.db import migrations, transaction

#: Os nossos 3D com as fotos no showroom (o Modelo 4 só tem as da fábrica; o Modelo 5, as vistas 3D).
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

    from core import categorias_capas
    from core.cadastro_modelos import CADASTROS, cadastrar, fotos_do_cadastro

    if not getattr(settings, "IS_RENDER", False):
        return
    Brinquedos = apps.get_model("core", "Brinquedos")
    for chave in CHAVES:
        dados = CADASTROS[chave]
        brinquedo = Brinquedos.objects.filter(nome_brinquedo=dados["nome"]).first()
        if brinquedo is None or not fotos_do_cadastro(brinquedo, chave):
            continue  # fora do catálogo (outra migração cadastra) ou com as fotos do painel
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
            avisar(f"As fotos do {dados['nome']} agora são as do showroom.")
        except Exception as erro:  # o deploy segue; o comando refaz depois
            avisar(f"As fotos do {dados['nome']} não foram refeitas agora ({erro!r}). "
                   f"Rode: python manage.py cadastrar_modelo_3d {chave} --fotos")
    categorias_capas.subir_fotos_no_deploy(apps, schema_editor, avisar=avisar)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0157_capas_em_cena_do_catalogo"),
    ]

    operations = [
        migrations.RunPython(refazer, migrations.RunPython.noop),
    ]
