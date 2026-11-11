"""As capas e as fotos das categorias em alta, no nível das imagens da fábrica (a 0155).

O cliente: "você é uma IA, não consegue fazer algo com melhor resolução e
mais coerência? ... veja os brinquedões que eu mandei, olha como estão as
imagens, maravilhosas.. nas categorias sim ponha as crianças, porém nas
fotos individuais não coloque as crianças". As imagens foram refeitas
(ferramentas/categorias; LEIA-ME, seção 60):
  * o render no dobro do tamanho e reduzido com o filtro Lanczos, a luz de
    ambiente PBR, as sombras macias em mapa grande, a oclusão de ambiente
    (GTAO) e as texturas desenhadas em alta;
  * as CAPAS dos produtos em 1600 x 1600, sem gente e sem outra máquina, no
    salão do mural (como as imagens da fábrica do Brinquedão Modelo 5);
  * as fotos das CATEGORIAS em 1600 x 1200, com as máquinas em fila e com
    espaço, nada atrás de móvel, e as crianças novas (redondas, com cabelo).

Esta, SÓ NO RENDER (o Cloudinary só está lá):
  * a galeria de cada produto com a capa em cena (a da 0153) que é a que o
    cadastro subiu (e não fotos postas pelo painel) é refeita À FORÇA --
    a capa nova tem o mesmo nome de arquivo, e a 0153 não subiria de novo;
  * sobem as fotos das categorias que mudaram (`atualizar_capas`: só as de
    assinatura nova).
Se uma subida falhar, o deploy segue e o aviso diz o comando:
    python manage.py cadastrar_modelo_3d <chave> --fotos
    python manage.py atualizar_capas_categorias
"""

from django.db import migrations, transaction

#: Os produtos com a capa em cena (o Brinquedão Modelo 5 tem a foto do salão da fábrica: fica).
CHAVES = (
    "brinquedao-modelo-2",
    "brinquedao-modelo-3",
    "brinquedao-ninja",
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
            avisar(f"A capa do {dados['nome']} agora é a nova, em alta.")
        except Exception as erro:  # o deploy segue; o comando refaz depois
            avisar(f"A capa do {dados['nome']} não foi trocada agora ({erro!r}). "
                   f"Rode: python manage.py cadastrar_modelo_3d {chave} --fotos")
    # as fotos das categorias (só as que mudaram; se falhar, avisa o comando)
    categorias_capas.subir_fotos_no_deploy(apps, schema_editor, avisar=avisar)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0154_basquete_e_air_game_reais"),
    ]

    operations = [
        migrations.RunPython(refazer, migrations.RunPython.noop),
    ]
